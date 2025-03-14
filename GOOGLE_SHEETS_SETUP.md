# Google Sheets Integration Setup Guide

This guide will help you set up the Google Sheets integration for the SEJU Stats Service.

## Prerequisites

- A Google account
- Access to the Google Cloud Console
- The SEJU Stats Service installed and running

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top of the page
3. Click on "New Project"
4. Enter a name for your project (e.g., "SEJU Stats Service")
5. Click "Create"

## Step 2: Enable the Google Sheets API

1. In your new project, go to the "APIs & Services" > "Library" section
2. Search for "Google Sheets API"
3. Click on "Google Sheets API"
4. Click "Enable"

## Step 3: Create a Service Account

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Enter a name for your service account (e.g., "SEJU Stats Service")
4. Click "Create and Continue"
5. For the role, select "Project" > "Editor"
6. Click "Continue"
7. Click "Done"

## Step 4: Create a Service Account Key

1. In the "Service Accounts" list, find the service account you just created
2. Click on the three dots menu at the end of the row
3. Click "Manage keys"
4. Click "Add Key" > "Create new key"
5. Select "JSON" as the key type
6. Click "Create"
7. The key file will be downloaded to your computer

## Step 5: Configure the SEJU Stats Service

1. Rename the downloaded key file to `service-account.json`
2. Move the file to the root directory of the SEJU Stats Service
3. Update your `.env` file with the following:

```env
# Google Sheets Configuration
GOOGLE_SERVICE_ACCOUNT_FILE=./service-account.json
GOOGLE_SHEETS_ID=1JHrIoReIXPsYJdfbcFdq1csHEH8HsoJkhin3wF5NkOs
GOOGLE_SHEETS_WORKSHEET=Auto Registro
```

## Step 6: Share the Google Sheet

1. Open the Google Sheet you want to use
2. Click the "Share" button in the top right corner
3. In the "Add people and groups" field, enter the email address of your service account
   - You can find this email in the `service-account.json` file under the `client_email` field
4. Make sure the service account has "Editor" access
5. Click "Share"

## Step 7: Test the Integration

1. Restart the SEJU Stats Service
2. Check the logs to verify that the Google Sheets integration is working:
   ```
   Google Sheets exporter initialized successfully
   ```
3. Wait for the service to process some custom games
4. Check the Google Sheet to see if the data is being exported

## Troubleshooting

### The service cannot connect to Google Sheets

Check the logs for error messages. Common issues include:

- The service account credentials file is not found
- The service account does not have access to the Google Sheet
- The Google Sheets API is not enabled for the project

### No data is being exported

Check the logs for error messages. Common issues include:

- No custom games are being found
- The worksheet name is incorrect
- The service account does not have write access to the Google Sheet

### Error: "The caller does not have permission"

This usually means that the service account does not have access to the Google Sheet. Make sure you have shared the Google Sheet with the service account email address and given it "Editor" access.

## Additional Configuration

### Using a Different Google Sheet

If you want to use a different Google Sheet, update the `GOOGLE_SHEETS_ID` environment variable with the ID of your Google Sheet. You can find the ID in the URL of the Google Sheet:

```
https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
```

### Using a Different Worksheet

If you want to use a different worksheet within the Google Sheet, update the `GOOGLE_SHEETS_WORKSHEET` environment variable with the name of your worksheet. 