# VectorShift Technical Assessment - Venkatarami Reddy

This project implements the **HubSpot OAuth 2.0 Integration** and **Contact Loading** features. It uses **FastAPI** for the backend and **React** for the frontend, with **Redis** for state/token management.

## Features Implemented

1. **HubSpot OAuth Flow**: Secure authorization using state validation and refresh tokens.
2. **Token Management**: Access tokens are securely exchanged and stored in Redis.
3. **Data Loading**: Fetches Contacts from HubSpot CRM and maps them to `IntegrationItem` objects.
4. **Security**: Environment variables used for sensitive credentials (Client ID/Secret).

## Prerequisites

* Node.js
* Python 3.9+
* Redis Server (Must be running)

## Setup Instructions

### 1. Backend

Navigate to the `/backend` directory:

```bash
cd backend
pip install -r requirements.txt
# Or manually: pip install fastapi uvicorn redis requests httpx python-multipart python-dotenv
```

**Environment Variables:**

Create a `.env` file in the `/backend` folder:

```env
HUBSPOT_CLIENT_ID=your_client_id_here
HUBSPOT_CLIENT_SECRET=your_client_secret_here
HUBSPOT_REDIRECT_URI=http://localhost:8000/integrations/hubspot/oauth2callback
```

Start the server:

```bash
uvicorn main:app --reload
```

### 2. Frontend

Navigate to the `/frontend` directory:

```bash
cd frontend
npm install
npm run start
```

## Usage

1. Open the UI at `http://localhost:3000`.
2. Select **HubSpot** from the integration dropdown.
3. Click **Connect to HubSpot** to complete the OAuth flow.
4. Once connected, click **Load Data** to fetch contacts.
