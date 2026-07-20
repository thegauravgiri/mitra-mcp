# Workspace Rules for Mitra MCP Agent

## Clockify Timesheet Filling Rules

1. **Weekday Only Schedule**:
   - Clockify entries MUST ONLY be filled from Monday to Friday.
   - Do NOT fill time entries for Saturday or Sunday unless explicitly commanded/specified by the user.

2. **Project Card Linkage Format**:
   - For project-related work, link the relevant card using description format: `<short_prefix>-<card_number>: <title>`
   - Example: Project name `gl-we-dhchat-....` maps to slug `dhchat`, resulting in entry description `dhchat-<card_number>: <title>`.

3. **Break Time Exclusion (1:30 PM to 3:00 PM)**:
   - Do NOT fill work time between 1:30 PM and 3:00 PM (13:30 to 15:00) as this period is designated break time.
   - Exceptions:
     - Proven work record exists in that time slot (e.g. WakaTime coding logs or Google Calendar meeting recorded between 13:30 and 15:00).
     - Explicitly specified by the user in the input prompt.

4. **Mandatory User Verification**:
   - ALWAYS ask and present the proposed fill plan to the user for verification/confirmation BEFORE creating any time entries in Clockify (`clockify_batch_create_entries`, `clockify_add_time_entry`, or `clockify_log_time_for_card`).
