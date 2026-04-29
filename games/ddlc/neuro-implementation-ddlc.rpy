init python:
    import os

    # Set game_over_action to "new_game" so that the game will automatically continue after the "end" of each "playthrough"
    neuro_set_config("game_over_action", "new_game")

    # Enable name entering at the start of the game
    def enter_name_func(data):
        name = data.get("name")
        if not name:
            return (False, "Please supply a valid name.")
        store.player = name
        neuro_unregister_action("enter_name")
        _neuro_ensure_show_screen("_neuro_finish_enter_name_screen")
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
            _neuro_delayed_function(
                0.1,
                _neuro_cancel_delayed_functions,
            )
    _neuro_load = new_neuro_load

    # Enable deletion of monika.chr at the end of the game
    def delete_file_func(data):
        filename = data.get("filename", None)
        if filename != "characters/monika.chr":
            return (False, "Cannot delete that file.")
        os.remove("characters/monika.chr")
        neuro_unregister_action("delete_file")
        return (True, "File deleted.")
    neuro_action_handlers["delete_file"] = delete_file_func

    def ddlc_new_label_callback(old_func, name, jumped):
        if old_func is not None:
            old_func(name, jumped)
        if name == "ch30_loop":
            neuro_register_action(
                "delete_file",
                "This action will allow you to delete a file from the game directory.",
                {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "enum": ["characters/monika.chr"]
                        }
                    },
                    "required": ["filename"]
                }
            )
    _neuro_override_func(config, "label_callback", ddlc_new_label_callback, "ddlc")

    # Overwrite currentuser and process_list on game save load
    def ddlc_new_say(old_func, who, what, interact=True, *args, **kwargs):
        if neuro_get_config("real_name") is not None:
            if what.startswith("I'm talking to {i}you{/i}, [player]."):
                store.currentuser = neuro_get_config("real_name")
                store.process_list = []
        if neuro_get_config("mention_swarm"):
            if what == "Where do I start...?":
                store.process_list = ["obs.exe"]
            elif what == "Um...hi, everyone!":
                what = "Um...hi, swarm! That's what you call them, right?"
            elif what == "Sorry, I can't exactly read your comments from here...":
                what = "Sorry, I can't exactly read chat from here..."
        return old_func(who, what, interact, *args, **kwargs)
    _neuro_override_func(renpy, "say", ddlc_new_say, "ddlc")

    # Give context about which character liked a word during the poem game
    def ddlc_new_show(old_func, name, *args, **kwargs):
        if "hop" in name:
            if name.startswith("s_sticker"):
                neuro_give_context("Chibi Sayori hopped in the lower left corner when you chose that word.", True)
            elif name.startswith("n_sticker"):
                neuro_give_context("Chibi Natsuki hopped in the lower left corner when you chose that word.", True)
            elif name.startswith("y_sticker"):
                neuro_give_context("Chibi Yuri hopped in the lower left corner when you chose that word.", True)
            elif name.startswith("m_sticker"):
                neuro_give_context("Chibi Monika hopped in the lower left corner when you chose that word.", True)
        
        return old_func(name, *args, **kwargs)
    _neuro_override_func(renpy, "show", ddlc_new_show, "ddlc")

screen _neuro_finish_enter_name_screen():
    zorder 3000
    modal False
    timer 3 action [Hide("_neuro_finish_enter_name_screen"), Function(FinishEnterName)]
