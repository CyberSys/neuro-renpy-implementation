init python:
    # Set game_over_action to "new_game" so that the game will automatically continue after the "end" of each "playthrough"
    neuro_set_config("game_over_action", "new_game")

    # Enable name entering at the start of the game
    def enter_name_func(data):
        name = data.get("name")
        if not name:
            return (False, "Please supply a valid name.")
        store.player = name
        renpy.show_screen("finish_enter_name_screen")
        return (True, "Name entered.")
    neuro_action_handlers["enter_name"] = enter_name_func
    
    original_neuro_load = _neuro_load
    def new_neuro_load(force_new_game=False):
        if getattr(persistent, "playername", None):
            original_neuro_load(force_new_game)
        else:
            renpy.show_screen("name_input", message="Please enter your name", ok_action=Function(FinishEnterName))
            neuro_register_action(
                "enter_name",
                "Please enter your name",
                {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                        }
                    },
                    "required": ["name"]
                }
            )
    _neuro_load = new_neuro_load

screen finish_enter_name_screen():
    zorder 1000
    modal False
    timer 3 action [Hide("finish_enter_name_screen"), Function(FinishEnterName)]
