"""
Test script for Admin Dashboard endpoints
Run this after the backend is running to verify admin endpoints work
"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000/v1"


async def test_admin_endpoints():
    async with httpx.AsyncClient() as client:
        print("=" * 70)
        print("ADMIN DASHBOARD ENDPOINT TESTS")
        print("=" * 70)
        
        # Step 1: Get admin token (dev-login)
        print("\n1️⃣  Getting admin token...")
        response = await client.get(f"{BASE_URL}/auth/dev-login")
        if response.status_code != 200:
            print(f"❌ Failed to get token: {response.text}")
            return
        
        data = response.json()
        token = data.get("access_token")
        print(f"✅ Got token for: {data['user']['email']}")
        print(f"   Role: {data['user']['role']}")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 2: Test /admin/system-stats (lightweight)
        print("\n2️⃣  Testing /admin/system-stats (quick stats)...")
        response = await client.get(f"{BASE_URL}/admin/system-stats", headers=headers)
        if response.status_code == 200:
            print("✅ Success")
            print(json.dumps(response.json(), indent=2, default=str))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
        
        # Step 3: Test /admin/dashboard (full dashboard)
        print("\n3️⃣  Testing /admin/dashboard (full backoffice)...")
        response = await client.get(f"{BASE_URL}/admin/dashboard", headers=headers)
        if response.status_code == 200:
            print("✅ Success")
            data = response.json()
            print("\nSummary:")
            print(json.dumps(data.get("summary", {}), indent=2))
            
            print("\nUser Stats:")
            print(json.dumps(data.get("user_stats", {}), indent=2))
            
            print("\nOrganization Stats:")
            print(json.dumps(data.get("organization_stats", {}), indent=2))
            
            print("\nMost Active Organizations:")
            orgs = data.get("system_health", {}).get("most_active_orgs", [])
            print(json.dumps(orgs, indent=2))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
        
        # Step 4: Test /admin/users
        print("\n4️⃣  Testing /admin/users (list all users)...")
        response = await client.get(f"{BASE_URL}/admin/users?skip=0&limit=10", headers=headers)
        if response.status_code == 200:
            print("✅ Success")
            users = response.json()
            print(f"   Found {len(users)} users (showing first 10)")
            for user in users[:3]:
                print(f"   • {user['email']} ({user['role']})")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
        
        # Step 5: Test /admin/organizations
        print("\n5️⃣  Testing /admin/organizations (list all orgs)...")
        response = await client.get(f"{BASE_URL}/admin/organizations?skip=0&limit=10", headers=headers)
        if response.status_code == 200:
            print("✅ Success")
            orgs = response.json()
            print(f"   Found {len(orgs)} organizations")
            for org in orgs:
                print(f"   • {org['name']} ({org['member_count']} members)")
                
                # Step 6: Test detailed org view
                print(f"\n6️⃣  Testing /admin/organizations/{org['id']}/details...")
                response = await client.get(
                    f"{BASE_URL}/admin/organizations/{org['id']}/details",
                    headers=headers
                )
                if response.status_code == 200:
                    print("   ✅ Success")
                    details = response.json()
                    stats = details.get("stats", {})
                    print(f"      Members: {stats.get('total_members')}")
                    print(f"      Documents: {stats.get('documents')}")
                    print(f"      Cases: {stats.get('cases')}")
                else:
                    print(f"   ❌ Failed: {response.status_code}")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
        
        # Step 7: Test authorization (should fail for non-admin)
        print("\n7️⃣  Testing authorization (try without admin role)...")
        # Get a regular user token
        response = await client.get(f"{BASE_URL}/auth/dev-login?email=user@example.com")
        if response.status_code == 200:
            data = response.json()
            user_token = data.get("access_token")
            user_headers = {"Authorization": f"Bearer {user_token}"}
            
            response = await client.get(f"{BASE_URL}/admin/dashboard", headers=user_headers)
            if response.status_code == 403:
                print("✅ Correctly rejected (403 Forbidden)")
            else:
                print(f"❌ Should be 403 but got {response.status_code}")
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETE")
        print("=" * 70)


if __name__ == "__main__":
    print("\n⚠️  Make sure the backend is running on http://localhost:8000")
    print("    Run: docker-compose up")
    print()
    asyncio.run(test_admin_endpoints())
