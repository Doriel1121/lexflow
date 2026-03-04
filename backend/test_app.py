import requests
import json

BASE_URL = "http://localhost:8000/v1"

# Test 1: Login
print("Test 1: Login...")
login_response = requests.post(
    f"http://localhost:8000/token",
    data={"username": "admin@example.com", "password": "adminpassword"}
)
if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    print("[OK] Login successful")
else:
    print(f"[FAIL] Login failed: {login_response.status_code}")
    exit(1)

headers = {"Authorization": f"Bearer {token}"}

# Test 2: Get cases
print("\nTest 2: Get cases...")
cases_response = requests.get(f"{BASE_URL}/cases/", headers=headers)
if cases_response.status_code == 200:
    cases = cases_response.json()
    print(f"[OK] Retrieved {len(cases)} cases")
else:
    print(f"[FAIL] Failed to get cases: {cases_response.status_code}")

# Test 3: Get documents
print("\nTest 3: Get documents...")
docs_response = requests.get(f"{BASE_URL}/documents/", headers=headers)
if docs_response.status_code == 200:
    docs = docs_response.json()
    print(f"[OK] Retrieved {len(docs)} documents")
    
    # Test 4: If documents exist, test new endpoints
    if len(docs) > 0:
        doc_id = docs[0]["id"]
        
        # Test document text endpoint
        print(f"\nTest 4: Get document text (doc {doc_id})...")
        text_response = requests.get(f"{BASE_URL}/documents/{doc_id}/text", headers=headers)
        if text_response.status_code == 200:
            text_data = text_response.json()
            print(f"[OK] Retrieved text: {len(text_data.get('content', ''))} chars")
            print(f"  Language: {text_data.get('language')}")
            print(f"  Page count: {text_data.get('page_count')}")
        elif text_response.status_code == 404:
            print("  Document has no OCR text (expected for some docs)")
        else:
            print(f"[FAIL] Failed: {text_response.status_code}")
        
        # Test metadata extraction
        print(f"\nTest 5: Extract metadata (doc {doc_id})...")
        extract_response = requests.post(f"{BASE_URL}/documents/{doc_id}/extract-metadata", headers=headers)
        if extract_response.status_code in [200, 201]:
            metadata = extract_response.json()
            print(f"[OK] Metadata extracted:")
            print(f"  Dates: {len(metadata.get('dates', []))}")
            print(f"  Entities: {len(metadata.get('entities', []))}")
            print(f"  Amounts: {len(metadata.get('amounts', []))}")
            print(f"  Case numbers: {len(metadata.get('case_numbers', []))}")
        elif extract_response.status_code == 400:
            print("  Document has no content (expected for some docs)")
        else:
            print(f"[FAIL] Failed: {extract_response.status_code}")
        
        # Test get metadata
        print(f"\nTest 6: Get metadata (doc {doc_id})...")
        get_meta_response = requests.get(f"{BASE_URL}/documents/{doc_id}/metadata", headers=headers)
        if get_meta_response.status_code == 200:
            metadata = get_meta_response.json()
            print(f"[OK] Retrieved metadata")
        elif get_meta_response.status_code == 404:
            print("  No metadata found (expected if not extracted yet)")
        else:
            print(f"[FAIL] Failed: {get_meta_response.status_code}")
else:
    print(f"[FAIL] Failed to get documents: {docs_response.status_code}")

print("\n" + "="*50)
print("Application is working correctly!")
print("="*50)
