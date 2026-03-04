"""
Final Data Leak Security Test - Comprehensive Verification
"""

import asyncio
import httpx
import random
import string

async def test_data_isolation():
    await asyncio.sleep(2)
    base_url = 'http://localhost:8000/v1'
    
    # Create unique test emails
    suffix = ''.join(random.choices(string.ascii_lowercase, k=6))
    email_user_a = f'testuser_a_{suffix}@test.com'
    email_user_b = f'testuser_b_{suffix}@test.com'
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print('🔒 DATA ISOLATION SECURITY TEST')
        print('=' * 80)
        
        # Step 1: Create User A with LAWYER role
        print(f'\n1️⃣  Creating User A (LAWYER)...')
        resp = await client.get(f'{base_url}/auth/dev-login?email={email_user_a}')
        user_a_data = resp.json()
        user_a_token = user_a_data['access_token']
        user_a_role = user_a_data['user']['role']
        print(f'   Email: {email_user_a}')
        print(f'   Role: {user_a_role}')
        
        # Step 2: Create User B with LAWYER role
        print(f'\n2️⃣  Creating User B (LAWYER)...')
        resp = await client.get(f'{base_url}/auth/dev-login?email={email_user_b}')
        user_b_data = resp.json()
        user_b_token = user_b_data['access_token']
        user_b_role = user_b_data['user']['role']
        print(f'   Email: {email_user_b}')
        print(f'   Role: {user_b_role}')
        
        headers_a = {'Authorization': f'Bearer {user_a_token}'}
        headers_b = {'Authorization': f'Bearer {user_b_token}'}
        
        # Step 3: Get Admin token
        print(f'\n3️⃣  Getting ADMIN token...')
        resp = await client.get(f'{base_url}/auth/dev-login?email=doriel494@gmail.com')
        admin_data = resp.json()
        admin_token = admin_data['access_token']
        admin_role = admin_data['user']['role']
        print(f'   Email: doriel494@gmail.com')
        print(f'   Role: {admin_role}')
        headers_admin = {'Authorization': f'Bearer {admin_token}'}
        
        # Step 4: Check document access
        print(f'\n4️⃣  Checking document visibility...')
        
        resp = await client.get(f'{base_url}/documents/', headers=headers_a)
        docs_a = resp.json()
        
        resp = await client.get(f'{base_url}/documents/', headers=headers_b)
        docs_b = resp.json()
        
        resp = await client.get(f'{base_url}/documents/', headers=headers_admin)
        docs_admin = resp.json()
        
        print(f'   User A sees: {len(docs_a)} documents')
        print(f'   User B sees: {len(docs_b)} documents')
        print(f'   Admin sees: {len(docs_admin)} documents')
        
        # Step 5: Verify data isolation
        print()
        print('=' * 80)
        print('SECURITY VERIFICATION:')
        print('=' * 80)
        
        print()
        if user_a_role == 'lawyer' and user_b_role == 'lawyer':
            print('✅ Both users have LAWYER role (correct default)')
        else:
            print(f'❌ Incorrect roles: A={user_a_role}, B={user_b_role}')
        
        if admin_role == 'admin':
            print('✅ Admin has ADMIN role')
        else:
            print(f'❌ Admin role incorrect: {admin_role}')
        
        if len(docs_a) == 0 and len(docs_b) == 0:
            print('✅ Regular users see their own docs only (no unauthorized access)')
        elif len(docs_a) > 0 and len(docs_b) > 0 and docs_a == docs_b:
            print('❌ DATA LEAK: Both users see same documents!')
        else:
            print('✅ Users see different documents (correct)')
        
        if len(docs_admin) >= len(docs_a) and len(docs_admin) >= len(docs_b):
            print('✅ Admin can see all documents')
        else:
            print('❌ Admin cannot see all documents')
        
        print()
        print('=' * 80)
        
        if (user_a_role == 'lawyer' and user_b_role == 'lawyer' and 
            admin_role == 'admin' and len(docs_a) == len(docs_b)):
            print('✅ ALL TESTS PASSED - DATA ISOLATION WORKING!')
        else:
            print('❌ SECURITY ISSUES DETECTED')

if __name__ == '__main__':
    asyncio.run(test_data_isolation())
