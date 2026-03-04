import asyncio
import httpx
import time

async def perform_e2e_test():
    # Helper to generate an admin token without relying on active browser cookies
    print("----- BACKGROUND AI PROCESSING TEST -----")
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Login to get token
        login_response = await client.post(
            "/v1/auth/login", # Directly querying the backend port bypasses NGINX /api
            data={"username": "doriel494@gmail.com", "password": "password123"}
        )
        if login_response.status_code != 200:
            print(f"FAILED TO LOGIN: {login_response.text}")
            return
            
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Upload a File
        print("Uploading a file...")
        start_time = time.time()
        
        # Test file payload
        files = {'file': ('partnership_agreement.txt', b'''
PARTNERSHIP AGREEMENT

This Partnership Agreement ("Agreement") is made this 15th day of October, 2026, by and between:
1. John Doe, residing at 123 Main St, Anytown, CA
2. Jane Smith, residing at 456 Oak Rd, Somewhere, NY

The parties hereby form a partnership to be known as "Dynamic Solutions LLC".
The initial capital contribution shall be $50,000 USD from each partner.

Obligations:
- John Doe is responsible for marketing.
- Jane Smith is responsible for software development.

Governing Law: California
''', 'text/plain')}
        
        upload_response = await client.post(
            "/v1/documents/?case_id=0",
            files=files,
            headers=headers
        )
        
        upload_duration = time.time() - start_time
        
        if upload_response.status_code != 201:
            print(f"FAILED TO UPLOAD: {upload_response.text}")
            return
            
        doc_data = upload_response.json()
        doc_id = doc_data['id']
        
        print(f"SUCCESS: Document {doc_id} uploaded in {upload_duration:.2f} seconds!")
        if upload_duration > 3.0:
            print("WARNING: Upload latency is still high! Background task may not be executing correctly.")
        else:
            print("LATENCY TEST PASSED: File uploaded instantly via FastApi BackgroundTasks.")
            
        print(f"Initial Status: {doc_data.get('processing_status')}")
        
        # 3. Poll for AI processing completion
        print("\nPolling backend for AI completion (Max 30s)...")
        max_attempts = 15
        for i in range(max_attempts):
            await asyncio.sleep(2)
            check_response = await client.get(f"/v1/documents/{doc_id}", headers=headers)
            current_doc = check_response.json()
            status = current_doc.get("processing_status")
            
            print(f"Attempt {i+1}: Status is '{status}'")
            
            if status == "completed":
                print("\nSUCCESS: Background AI processing completed successfully!")
                break
            elif status == "failed":
                print("\nERROR: Background processing failed.")
                break
                
            if i == max_attempts - 1:
                print("\nTIMEOUT: Document is still processing after 30 seconds.")

        # 4. Verify AI Knowledge Extraction & Db Chunks
        intel_response = await client.get(f"/v1/documents/{doc_id}/intelligence", headers=headers)
        intel = intel_response.json()
        if intel.get('summary') and intel.get('metadata', {}).get('amounts'):
            print("AI INTELLIGENCE TEST PASSED: Entities and Summaries successfully extracted via LLM in background.")
        else:
            print("WARNING: Missing AI Intelligence data.")
            
if __name__ == "__main__":
    asyncio.run(perform_e2e_test())
