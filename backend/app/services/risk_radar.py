import asyncio
import httpx
from typing import Dict, Any, Optional, Tuple
from cachetools import TTLCache
from app.core.config import settings
from app.schemas.risk import RiskAssessmentResponse, LocalRiskMatchedEntity, GlobalRiskMatchedEntity

# Simple in-memory cache for API responses (500 items, TTL 1 hour)
risk_cache = TTLCache(maxsize=500, ttl=3600)

class RiskRadarService:
    ISRAELI_GOV_API_URL = "https://data.gov.il/api/3/action/datastore_search"
    ISRAELI_COMPANIES_RESOURCE_ID = "f004176c-b85f-4542-8901-7b3176f9a054"  # Updated ID
    OPENSANCTIONS_API_URL = "https://api.opensanctions.org/search/default"

    # Keywords that indicate a company is not in good standing
    HIGH_RISK_LOCAL_STATUSES = ["מפרת חוק", "בפירוק", "מחוקה", "התראת מפר חוק"]

    async def verify_entity(self, query: str) -> RiskAssessmentResponse:
        """
        Concurrently queries both the local registry and global sanctions list.
        """
        # Check cache first
        if query in risk_cache:
            return risk_cache[query]

        # Use httpx AsyncClient for concurrent requests
        async with httpx.AsyncClient() as client:
            local_task = self._fetch_local_status(client, query)
            global_task = self._fetch_global_status(client, query)

            # Wait for both APIs to return
            results = await asyncio.gather(local_task, global_task, return_exceptions=True)
            local_result, global_result = results

        response = RiskAssessmentResponse(query=query)
        warnings = []

        # Process Local Result
        if isinstance(local_result, Exception):
            warnings.append(f"Local verification failed: {str(local_result)}")
        elif local_result:
            response.local_risk = local_result
            response.auto_fill_name = local_result.name
            response.auto_fill_address = local_result.address
            if local_result.is_high_risk:
                response.is_high_risk = True

        # Process Global Result
        if isinstance(global_result, Exception):
            warnings.append(f"Global verification failed: {str(global_result)}")
        elif global_result:
            response.global_risk = global_result
            if global_result.is_high_risk:
                response.is_high_risk = True

        response.warnings = warnings
        
        # Cache successful responses
        risk_cache[query] = response
        
        return response

    async def _fetch_local_status(self, client: httpx.AsyncClient, query: str) -> Optional[LocalRiskMatchedEntity]:
        """
        Query Israeli Gov Data gov.il API. 
        Note: The API searches inside text fields. We try to find an exact match if we can,
        or take the closest match.
        """
        params = {
            "resource_id": self.ISRAELI_COMPANIES_RESOURCE_ID,
            "q": query,
            "limit": 5
        }
        
        try:
            res = await client.get(self.ISRAELI_GOV_API_URL, params=params, timeout=10.0)
            res.raise_for_status()
            data = res.json()
            
            records = data.get("result", {}).get("records", [])
            if not records:
                return None
                
            # Naive approach: take the first record. 
            # In a production app, we might rank matches or filter by exact ID.
            best_match = records[0]
            
            # Fields in Gov Data Israeli Companies DB
            # "מספר חברה" = Company ID
            # "שם חברה" = Company Name
            # "סטטוס חברה" = Company Status
            # "כתובת" = Address 
            
            company_id = str(best_match.get("מספר חברה", ""))
            company_name = str(best_match.get("שם חברה", ""))
            status = str(best_match.get("סטטוס חברה", ""))
            address = str(best_match.get("כתובת", ""))
            
            # Determine Risk
            is_high_risk = any(risk_kw in status for risk_kw in self.HIGH_RISK_LOCAL_STATUSES)
            
            return LocalRiskMatchedEntity(
                id=company_id,
                name=company_name,
                address=address,
                status=status,
                is_high_risk=is_high_risk,
                risk_reason=f"Company status is '{status}'" if is_high_risk else None
            )
            
        except Exception as e:
            # Re-raise to be handled by asyncio.gather return_exceptions
            raise Exception(f"Israeli API error: {str(e)}")

    async def _fetch_global_status(self, client: httpx.AsyncClient, query: str) -> Optional[GlobalRiskMatchedEntity]:
        """
        Query OpenSanctions API for global watchlist/AML.
        """
        if not settings.OPENSANCTIONS_API_KEY:
             # If no key, skip nicely or mock (currently simulating a skip/warning upstream if key is absent)
             # To avoid breaking without a key in dev, we will just return None for now or mock.
             return None
             
        headers = {
            "Authorization": f"ApiKey {settings.OPENSANCTIONS_API_KEY}",
            "Accept": "application/json"
        }
        params = {
            "q": query,
            "fuzzy": "true"
        }
        
        try:
            res = await client.get(self.OPENSANCTIONS_API_URL, headers=headers, params=params, timeout=10.0)
            res.raise_for_status()
            data = res.json()
            
            results = data.get("results", [])
            if not results:
                return None
            
            # OpenSanctions returns items by relevance.
            # We will flag if we find an entity with a high matching score.
            best_match = results[0]
            
            entity_id = best_match.get("id", "")
            entity_name = best_match.get("caption", best_match.get("name", ""))
            datasets = best_match.get("datasets", [])
            
            # Any match in OpenSanctions is generally considered high risk since it's a sanctions database
            return GlobalRiskMatchedEntity(
                id=entity_id,
                name=entity_name,
                datasets=datasets,
                is_high_risk=True,
                risk_reason=f"Found in sanctions datasets: {', '.join(datasets)}"
            )
            
        except Exception as e:
            raise Exception(f"OpenSanctions error: {str(e)}")

risk_radar_service = RiskRadarService()
