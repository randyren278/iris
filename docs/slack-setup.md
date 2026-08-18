# Iris Slack Socket Mode setup

S0 is a one-time, operator-authenticated setup. Iris uses a private Slack
workspace and an outbound Socket Mode connection; it does not expose an HTTP
listener or accept tokens from files, environment variables, prompts, or chat.

1. Create or select a private Slack workspace and create an app named `Iris`.
2. Enable **Socket Mode**, create an app-level token with the
   `connections:write` scope, and copy it once.
3. Under **OAuth & Permissions**, add only the bot scopes `chat:write`,
   `im:history`, and `im:read`; install the app to the workspace and copy the
   bot token once.
4. Start a direct message with the Iris bot. In **Event Subscriptions**, enable
   events and subscribe to the bot event `message.im`.
5. Store the tokens in the **login** Keychain using **Keychain Access**. Add
   two Password items (File → New Password Item):

   | Name | Account Name | Password |
   | --- | --- | --- |
   | `com.iris.slack` | `iris-app-token` | the `xapp-…` token |
   | `com.iris.slack` | `iris-bot-token` | the `xoxb-…` token |

   Use the Keychain UI rather than a shell command so neither token appears in
   shell history or a process command line. Replace any existing matching Iris
   item rather than creating duplicates.

6. Run the local credential and Socket Mode check:

   ```sh
   .venv/bin/python -m iris.slack_probe
   ```

At this point, report the real result for CP-S0. Do not place either token in
`config.toml`, a `.env` file, the repository, command-line arguments, or a DM.
The DM round-trip is completed by the S1 Slack transport and then re-run as the
CP-S0 live check.
