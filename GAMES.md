# Games
This list includes every game the mod was tested with.
Read for each game how well the mod works with the game and recommendations for running the mod with that game.
If you test the mod on a game which is not yet included in this list, feel free to add the game and your experience to this list via pull request.
You may also add some information to the games already listed.


## Doki Doki Literature Club!
A [game-specific implementation](https://github.com/caheuer/neuro-renpy-implementation/releases/latest/download/neuro-ddlc-implementation.zip) exists for this game.

### Context
All context on the dialogue and poems are given.
Some non-crucial audiovisual context to the game is missing, such as special fonts, music changing or visual changes.

### Interaction
Neuro can play this game start-to-end without any intervention.

### Recommendations
- Use only the game-specific implementation and its accompanying `neuroconfig.py`
- If the game has been previously opened, delete the folder `C:\Users\[username]\AppData\Roaming\RenPy\DDLC-1454445547`


## MILK INSIDE A BAG OF MILK INSIDE A BAG OF MILK
The mod works well with this game.

### Context
All dialogue context is given, however some audiovisual storytelling is missing.

### Interaction
Neuro will be able to completely interact with this game.
However, this includes a language selection at the start of the game.
Neuro CAN choose a language other than English, so be aware of this.

### Recommendations
- Set `save_game` in the config file to `False`


## Slay the Princess — The Pristine Cut
The mod works well with this game when recommendations are observed.

### Context
All dialogue context is given, however some audiovisual storytelling is missing.

### Interaction
Neuro will be able to completely interact with this game.
This includes links to the game's Discord and other links at the very end so beware of this — human intervention to end the game is necessary here otherwise external links will be opened non-stop.

### Recommendations
- Set `save_game` in the config file to `True`
- Set `game_over_action` in the config file to `new_game`
- The game has recorded voice lines. To ensure they are played completely it is recommended to set `wait_for_voiceover = True` in `neuroconfig.py` (which it is by default)