import asyncio
import httpx

async def test_data_leak():
    await asyncio.sleep(2)  # Wait for backend to start
    base_url = 'http://localhost:8000/v1'
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Get testdoriel token
        resp = await client.get(f'{base_url}/auth/dev-login?email=testdoriel@gmail.com')
        if resp.status_code != 200:
            print(f'Error: {resp.status_code} - {resp.text}')
            return
        testdoriel_token = resp.json()['access_token']
        testdoriel_role = resp.json()['user']['role']
        
        # Get admin token  
        resp = await client.get(f'{base_url}/auth/dev-login?email=doriel494@gmail.com')
        if resp.status_code != 200:
            print(f'Error: {resp.status_code} - {resp.text}')
            return
        admin_token = resp.json()['access_token']
        admin_role = resp.json()['user']['role']
        
        headers_testdoriel = {'Authorization': f'Bearer {testdoriel_token}'}
        headers_admin = {'Authorization': f'Bearer {admin_token}'}
        
        print('🔍 Data Leak Security Test')
        print('=' * 80)
        
        # Test 1: testdoriel sees their documents
        resp = await client.get(f'{base_url}/documents/', headers=headers_testdoriel)
        if resp.status_code != 200:
            print(f'Error getting testdoriel docs: {resp.status_code}')
            print(resp.text)
            return
        testdoriel_docs = resp.json()
        print(f'\n1️⃣  testdoriel@gmail.com (role: {testdoriel_role}) sees {len(testdoriel_docs)} documents:')
        for doc in testdoriel_docs:
            print(f'   • {doc["filename"]}')
        
        # Test 2: admin sees documents
        resp = await client.get(f'{base_url}/documents/', headers=headers_admin)
        if resp.status_code != 200:
            print(f'Error getting admin docs: {resp.status_code}')
            print(resp.text)
            return
        admin_docs = resp.json()
        print(f'\n2️⃣  doriel494@gmail.com (role: {admin_role}) sees {len(admin_docs)} documents:')
        for doc in admin_docs:
            print(f'   • {doc["filename"]}')
        
        # Test 3: Create a new user and check isolation
        new_docs = []
        print(f'\n3️⃣  Creating new user and checking data isolation...')
        
        resp = await client.get(f'{base_url}/auth/dev-login?email=newuser@test.com')
        if resp.status_code != 200:
            print(f'   Error creating new user: {resp.status_code}')
        else:
            new_user_token = resp.json()['access_token']
            new_user_role = resp.json()['user']['role']
            headers_new = {'Authorization': f'Bearer {new_user_token}'}
            
            resp = await client.get(f'{base_url}/documents/', headers=headers_new)
            new_docs = resp.json()
            print(f'   newuser@test.com (role: {new_user_role}) sees {len(new_docs)} documents')
        
        print()
        print('=' * 80)
        print('SECURITY ANALYSIS:')
        print(f'  • testdoriel docs: {len(testdoriel_docs)}')
        print(f'  • admin docs: {len(admin_docs)}')
        print(f'  • new user docs: {len(new_docs)}')
        
        if len(new_docs) == 0 and len(testdoriel_docs) > 0 and len(admin_docs) > 0:
            print('\n✅ DATA ISOLATION WORKING:')
            print('   - New user sees 0 documents (correct - they have no uploads)')
            print('   - testdoriel sees their uploads')
            print('   - Admin sees all documents')
        else:
            print('\n⚠️  POTENTIAL ISSUE:')
            if len(new_docs) > 0:
                print('   - New user can see documents they did not upload!')
            if len(admin_docs) != len(testdoriel_docs):
                print('   - Admin is seeing different data than expected')

if __name__ == '__main__':
    asyncio.run(test_data_leak())
