# Discord Bot Project

A full-featured Discord bot comprising Ticket System, Moderation, and Pre-built messages.

## Features
- **Tickets**: Advanced ticket system with reason selection, transcripts, and status panels.
- **Moderation**: Warns, bans, kicks, and logging. Automod for invite links and bad words.
- **Snippets**: Pre-built messages with placeholder support for quick responses.
- **PostgreSQL**: Robust database suitable for future web panel integration.

## Setup

1.  **Prerequisites**:
    -   Python 3.9+
    -   PostgreSQL Database installed and running.

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    -   Rename `.env.example` (or similar) to `.env`.
    -   Fill in `DISCORD_TOKEN`, `DB_HOST`, `DB_PASSWORD`, etc.

4.  **Database**:
    -   Create a database (e.g., `discordbot`) in PostgreSQL.
    -   The bot will automatically apply the schema on first run.

5.  **Run**:
    ```bash
    python bot.py
    ```

## Usage

### Tickets
-   `/setup_ticket_panel [channel]`: Sends the "Open Ticket" panel.
-   `/add_ticket_reason [label] [category]`: Configure ticket reasons.

### Moderation
-   `/warn`, `/kick`, `/ban`
-   `/config set_logging [channel]`: Set where logs go.

### Snippets
-   `/create_snippet [name] [category] [content]`: Create a canned response.
-   `/snippet [category]`: Send a message.

