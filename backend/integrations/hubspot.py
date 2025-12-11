# backend/integrations/hubspot.py

import json
import secrets
import os
from dotenv import load_dotenv
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv()

CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID')
CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET')
REDIRECT_URI = os.getenv('HUBSPOT_REDIRECT_URI')
AUTHORIZATION_URL = 'https://app.hubspot.com/oauth/authorize'
TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'
encoded_scope = 'crm.objects.contacts.read%20oauth'

async def authorize_hubspot(user_id, org_id):
    """
    Constructs the HubSpot OAuth URL.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="HubSpot credentials not configured in .env")

    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)

    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)

    auth_url = (
        f"{AUTHORIZATION_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={encoded_scope}"
        f"&state={encoded_state}"
    )
    return auth_url

async def oauth2callback_hubspot(request: Request):
    """
    Handles the callback, validates state, exchanges code for token.
    """
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))

    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')

    if not encoded_state:
        raise HTTPException(status_code=400, detail="State missing")

    state_data = json.loads(encoded_state)
    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')
    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': REDIRECT_URI,
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}'),
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to get token: {response.text}")

    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)
    
    return HTMLResponse(content="<html><script>window.close();</script></html>")

async def get_hubspot_credentials(user_id, org_id):
    """
    Retrieves credentials from Redis.
    """
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials

def create_integration_item_metadata_object(result_json):
    """
    Maps HubSpot Contact to IntegrationItem.
    """
    props = result_json.get('properties', {})
    firstname = props.get('firstname', '')
    lastname = props.get('lastname', '')
    
    name = f"{firstname} {lastname}".strip()
    if not name:
        name = props.get('email', 'Unknown Contact')

    return IntegrationItem(
        id=result_json.get('id'),
        type='Contact',
        name=name,
        creation_time=props.get('createdate'),
        last_modified_time=props.get('lastmodifieddate'),
    )

async def refresh_access_token(refresh_token):
    """
    Helper function to refresh the access token using the refresh_token.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
    
    if response.status_code == 200:
        return response.json().get('access_token')
    return None

async def get_items_hubspot(credentials):
    """
    Fetches contacts using the access token.
    """
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    refresh_token = credentials.get('refresh_token')
    
    url = 'https://api.hubapi.com/crm/v3/objects/contacts?properties=firstname,lastname,email,createdate,lastmodifieddate'
    
    updated_credentials = None
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers={'Authorization': f'Bearer {access_token}'})
        
        if response.status_code == 401 and refresh_token:
            new_access_token = await refresh_access_token(refresh_token)
            
            if new_access_token:
                credentials['access_token'] = new_access_token
                updated_credentials = json.dumps(credentials)
                response = await client.get(url, headers={'Authorization': f'Bearer {new_access_token}'})
            else:
                print("Failed to refresh token.")

    if response.status_code == 200:
        results = response.json().get('results', [])
        items = [create_integration_item_metadata_object(res) for res in results]
        print(f"HubSpot Items Loaded: {[item.name for item in items]}")
        return items, updated_credentials
    
    print(f"Error fetching HubSpot items: {response.status_code} - {response.text}")
    return [], None