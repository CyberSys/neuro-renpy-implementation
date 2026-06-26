### GENERAL ###

# The WebSocket URL for the Neuro API
ws_url = "ws://localhost:8000"
# If the game should start automatically
# If set to true, the game will start with the last saved state (if save_game is set to true) or start a new game if no save was found
auto_start = True
# Whether or not to save the game automatically
# This also affects whether an auto-started game will load the last saved state
save_game = True
# Whether to save the game log
# If set to true, the game log will be saved to a file named "neuro_log.txt"
# Use this to debug the Neuro API interactions
save_log = False

### CONTEXT ###

# Whether to give context (dialogue and choices) to the Neuro API
give_context = True
# Whether the dialogue context should be silent
silent_dialogue = True
# Whether context about interactions, such as choices or custom screens with interaction, should be silent
silent_choices = False


### INTERACTION ###

# How progression to the next dialogue line should occur
# Options: "action" (sends an action "progress_dialogue" to the Neuro API), "auto" (time-based), "none" (user must click to progress)
progression_mode = "auto"
# At a minimum, how long should it take before the Neuro API can progress to the next dialogue line (in seconds)
# This has no effect if progression_mode is set to "auto" or "none"
min_progression_time = 2.0
# At a maximum, how long should it take before progressing to the next dialogue line (in seconds)
# If progression_mode is set to "action", this is the maximum time the Neuro API has to respond before the action is forced
# If progression_mode is set to "auto", this is the time before the next dialogue line is automatically shown
max_progression_time = 5.0
# Whether the Neuro API should be able to interact whenever there is a choice to be made, such as in the choices menu or custom screens
allow_interaction = True
# At a minimum, how long should it take before the Neuro API can interact on screens such as the choices menu (in seconds)
min_interaction_time = 5.0
# At a maximum, how long should it take before an interaction action is forced (in seconds)
max_interaction_time = 60.0


### DDLC SPECIFIC ###

# Give extra context at certain points in the game to describe what is happening on screen
on_screen_context = True
# If set to True, the game will always branch off to a special branch which is usually triggered when OBS runs.
# It will also change a bit what Monika says, referencing the swarm
mention_swarm = True
# In the last chapter, the game will try to read the "real" name of the player from PC settings.
# This "real" name can be set here. By setting a value here, the game will also skip the safety check for streaming.
real_name = "Neuro"