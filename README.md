# LINE Bot Webhook for GPT Integration

This project is a LINE Bot webhook that integrates with a GPT model to provide intelligent responses.

## Configuration

To run this project, you need to set up the following environment variables.

### Mandatory Environment Variables

*   **`LINE_ACCESS_TOKEN`**: Your LINE Channel Access Token. This is required for the bot to communicate with the LINE Messaging API.

    To set this variable:
    1.  Create a `.env` file in the root of the project.
    2.  Add the following line to the `.env` file, replacing `your_line_channel_access_token` with your actual token:
        ```
        LINE_ACCESS_TOKEN=your_line_channel_access_token
        ```

### Other Environment Variables

*   **`LINE_CHANNEL_SECRET`**: Your LINE Channel Secret. This is used to verify webhook requests from LINE.
    Set this in your `.env` file as:
    ```
    LINE_CHANNEL_SECRET=your_line_channel_secret
    ```

*   **`OPENAI_MODEL`** (Optional): The OpenAI model to be used. Defaults to `gpt-4.1-mini` if not set.
    You can set this in your `.env` file, for example:
    ```
    OPENAI_MODEL=gpt-4
    ```

*   **`GAS_LOG_URL`** (Optional): URL of your Google Apps Script endpoint to store chat logs.
    Set it in your `.env` file as:
    ```
    GAS_LOG_URL=https://script.google.com/your-script-url
    ```

*   **`TWILIO_ACCOUNT_SID`**, **`TWILIO_AUTH_TOKEN`**, **`TWILIO_WHATSAPP_NUMBER`** (Optional): Credentials for sending WhatsApp messages via Twilio.
    Example configuration:
    ```
    TWILIO_ACCOUNT_SID=your_account_sid
    TWILIO_AUTH_TOKEN=your_auth_token
    TWILIO_WHATSAPP_NUMBER=+1234567890
    ```

### WhatsApp Endpoint

The `/whatsapp` endpoint allows this bot to handle messages from a Twilio WhatsApp number. Configure the above Twilio environment variables and set the webhook URL in your Twilio console to point to `/whatsapp`.
