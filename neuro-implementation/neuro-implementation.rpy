init -1 python:
    DEFAULT_RENPY_SCREENS = {
        # in-game
        "say","choice","input","nvl","nvl_choice","notify","skip_indicator","ctc","keymap_screen",
        # menus/system
        "main_menu","navigation","save","load","preferences",
        "help","history","file_picker","joystick_preferences","quick_menu"
    }

    class Empty(object):
        pass

    import neuroconfigdefault
    try:
        import neuroconfig
        if hasattr(neuroconfig, "save_log") and neuroconfig.save_log:
            config.log = "neuro_log.txt"
    except ImportError:
        neuroconfig = Empty()
        if neuroconfigdefault.save_log:
            config.log = "neuro_log.txt"
        renpy.log("[NEURO] Failed to load neuroconfig.py")

    renpy.log("[NEURO] Initializing Neuro Implementation...")
    
    persistent._neuro_game_started = False
    persistent._neuro_shutdown_requested = False

    try:
        __import__("hmac")
    except:
        renpy.log("[NEURO] Module hmac not found, trying to import from py2...")
        from py2 import hmac as hmac2
        sys.modules["hmac"] = hmac2

    try:
        __import__("ssl")
    except:
        renpy.log("[NEURO] Module ssl not found, trying to import from py2...")
        from py2 import ssl as ssl2
        sys.modules["ssl"] = ssl2

    import websocket
    import json
    import time
    import types
    import re
    import renpy as r

    ### CONFIGURATION ###
    def neuro_get_config(key):
        ret = getattr(neuroconfig, key, None)
        if ret is None:
            ret = getattr(neuroconfigdefault, key, None)
        return ret

    def neuro_set_config(key, value, override_user_config=False):
        if override_user_config:
            setattr(neuroconfig, key, value)
        else:
            setattr(neuroconfigdefault, key, value)

    ### HELPER FUNCTIONS ###

    def _neuro_get_game_name():
        global _neuro_game_name
        try:
            if not _neuro_game_name:
                _neuro_game_name = renpy.config.name
        except:
            _neuro_game_name = renpy.config.name
        finally:
            return _neuro_game_name

    def _neuro_await_ws_connected(func, *args, **kwargs):
        if _neuro_ws and _neuro_ws.sock and _neuro_ws.sock.connected:
            func(*args, **kwargs)
        else:
            _neuro_delayed_function(
                1.0,
                _neuro_await_ws_connected,
                func,
                *args,
                **kwargs
            )

    def _neuro_delayed_function(delay, function, *args, **kwargs):
        # Delay cannot be less than or equal to zero
        delay = 0.1 if delay <= 0.0 else delay
        # We use ten different screens to allow multiple delayed functions to be scheduled at the same time
        global _neuro_delayed_function_screens_active
        if "_neuro_delayed_function_screens_active" not in globals():
            _neuro_delayed_function_screens_active = [False, False, False, False, False, False, False, False, False, False]
        index = None
        for i in range(10):
            if _neuro_delayed_function_screens_active[i]:
                index = None
            elif index is None:
                index = i
        if index is None:
            raise Exception("No available screens to schedule the delayed function. Maximum number of concurrent delayed functions is 10.")
        _neuro_delayed_function_screens_active[index] = True
        screen_name = "_neuro_delayed_function_screen_" + str(index)
        _neuro_ensure_show_screen(screen_name, delay, function, args, kwargs)

    def _neuro_cancel_delayed_functions():
        renpy.hide_screen("_neuro_delayed_function_screen_0")
        renpy.hide_screen("_neuro_delayed_function_screen_1")
        renpy.hide_screen("_neuro_delayed_function_screen_2")
        renpy.hide_screen("_neuro_delayed_function_screen_3")
        renpy.hide_screen("_neuro_delayed_function_screen_4")
        renpy.hide_screen("_neuro_delayed_function_screen_5")
        renpy.hide_screen("_neuro_delayed_function_screen_6")
        renpy.hide_screen("_neuro_delayed_function_screen_7")
        renpy.hide_screen("_neuro_delayed_function_screen_8")
        renpy.hide_screen("_neuro_delayed_function_screen_9")
        global _neuro_delayed_function_screens_active
        _neuro_delayed_function_screens_active = [False, False, False, False, False, False, False, False, False, False]

    def _neuro_cancel_delayed_function(index):
        renpy.hide_screen("_neuro_delayed_function_screen_" + str(index))
        global _neuro_delayed_function_screens_active
        if 0 <= index < len(_neuro_delayed_function_screens_active):
            _neuro_delayed_function_screens_active[index] = False

    def _neuro_ensure_show_screen(screen_name, *args, **kwargs):
        while True:
            s = renpy.get_screen(screen_name)
            if s:
                return s
            renpy.show_screen(screen_name, *args, **kwargs)
            renpy.restart_interaction()

    def _neuro_override_func(owner, func_name, new_func, override_id="default"):
        old_func = getattr(owner, func_name)

        if getattr(old_func, "_neuro_override", None) == override_id:
            return

        def f(*args, **kwargs):
            return new_func(old_func, *args, **kwargs)

        f._neuro_override = override_id if override_id is not None else "default"

        setattr(owner, func_name, f)

    def _neuro_clean_str(s):
        s = renpy.exports.substitute(s) # Translations and variables
        s = re.sub(r"\{.*?\}", "", s) # Ren'Py style tags
        s = re.sub(r"[ ]{2,}", " ", s) # Remove multiple spaces
        s = re.sub(r" *\n *", "\n", s) # Remove spaces around newlines
        s = s.strip() # Remove leading/trailing spaces and newlines
        return s

    def _neuro_find_buttons_in_displayble(displayable):
        results = []
        if isinstance(displayable, renpy.display.behavior.Button):
            results.append(displayable)
        if hasattr(displayable, "children"):
            for child in displayable.children:
                results += _neuro_find_buttons_in_displayble(child)
        return results

    def _neuro_get_displayable_text(displayable):
        text_parts = []
        if hasattr(displayable, "text"):
            text_parts.extend(displayable.text)
        if hasattr(displayable, "children"):
            for child in displayable.children:
                text_parts.append(_neuro_get_displayable_text(child))
        text_parts = [_neuro_clean_str(str(text)) for text in text_parts if str(text).strip()]
        return " ".join(text_parts) if text_parts else ""

    def _neuro_who_to_str(who):
        if who is None:
            return "Narrator"
        elif isinstance(who, str):
            return renpy.translate_string(who)
        elif hasattr(who, "name"):
            if who.name is None:
                return "Narrator"
            try:
                return renpy.translate_string(who.name)
            except:
                return str(who)
        else:
            return str(who)

    def _neuro_leave_game(force=False):
        persistent._neuro_shutdown_requested = True
        if not _can_save() and not force:
            return
        renpy.log("[NEURO] Leaving the game and returning to the main menu...")
        neuro_give_context("Leaving the game and returning to the main menu.")
        _neuro_cancel_delayed_functions()
        neuro_unregister_all_actions()
        _neuro_save()
        _neuro_delayed_function(
            0.1,
            renpy.full_restart
        )
        msg = {
            "command": "shutdown/ready",
            "game": _neuro_get_game_name(),
        }
        _neuro_send_ws_message(json.dumps(msg))

    def _neuro_is_voiceover_playing():
        channels = renpy.audio.audio.channels
        for name, channel in channels.items():
            is_voiceover = False
            if getattr(channel, "mixer", None) == "voice":
                is_voiceover = True
            if "vo" in str(name).lower():
                is_voiceover = True
            if is_voiceover and channel.get_playing():
                return True

    def _neuro_call_func_after_voiceover(func, *args, **kwargs):
        if neuro_get_config("wait_for_voiceover") and _neuro_is_voiceover_playing():
            _neuro_delayed_function(
                1.0,
                _neuro_call_func_after_voiceover,
                func,
                *args,
                **kwargs
            )
        else:
            func(*args, **kwargs)

    def _neuro_can_skip():
        if not neuro_get_config("allow_interaction"):
            return False

        if not neuro_get_config("allow_skipping"):
            return False

        if not config.allow_skipping:
            return False

        if not Skip().get_sensitive():
            return False

        try:
            if renpy.get_statement_name() not in ("say", "say-nvl"):
                return False

            return renpy.seen_current(True)
        except Exception:
            return True

    ### SAVING / LOADING ###

    def _can_save():
        if main_menu:
            return False
        try:
            return config.save and (renpy.context_nesting_level() == 0)
        except:
            # Older Ren'Py versions don't have config.save or renpy.context_nesting_level, so just assume we can save
            return True

    def _neuro_save():
        if not neuro_get_config("save_game"):
            return
        if not persistent._neuro_game_started:
            renpy.log("[NEURO] Game has not started yet, skipping save.")
            return
        if not _can_save():
            return
        renpy.log("[NEURO] Saving the game...")
        try:
            renpy.save("neuro-1")
        except Exception as e:
            renpy.log("[NEURO] Failed to save the game: {}".format(str(e)))

    def _neuro_can_load():
        return renpy.can_load(renpy.newest_slot())

    def _neuro_load(force_new_game=False):
        if renpy.can_load(renpy.newest_slot()) and not force_new_game and neuro_get_config("save_game"):
            # Load the last saved state
            neuro_give_context("Loading your last saved state. You will start off where you left off.", silent=True)
            renpy.load(renpy.newest_slot())
            neuro_give_context("Loading your last saved state failed. Starting a new game instead.", silent=True)
            renpy.log("[NEURO] Failed to load the last saved state")
        # Start a new game if no save was found or force_new_game is True or save_game in neuroconfig is False
        renpy.jump_out_of_context("start")


    ### CONTEXT ###

    def neuro_give_context(message, silent=False):
        if not neuro_get_config("give_context"):
            return
        msg = {
            "command": "context",
            "game": _neuro_get_game_name(),
            "data": {
                "message": message,
                "silent": silent
            }
        }
        _neuro_send_ws_message(json.dumps(msg))


    ### ACTIONS ###

    _neuro_registered_actions = []

    def neuro_register_action(action_name, action_description, action_schema):
        renpy.log("[NEURO] Registering action: {}".format(action_name))
        neuro_unregister_action(action_name)  # Unregister if already registered
        action = {
            "name": action_name,
            "description": action_description,
            "schema": action_schema
        }
        _neuro_registered_actions.append(action)
        msg = {
            "command": "actions/register",
            "game": _neuro_get_game_name(),
            "data": {
                "actions": [
                    action
                ]
            }
        }
        _neuro_send_ws_message(json.dumps(msg))

    def neuro_unregister_action(action_name):
        renpy.log("[NEURO] Unregistering action: {}".format(action_name))
        _neuro_registered_actions[:] = [action for action in _neuro_registered_actions if action["name"] != action_name]
        msg = {
            "command": "actions/unregister",
            "game": _neuro_get_game_name(),
            "data": {
                "action_names": [action_name]
            }
        }
        _neuro_send_ws_message(json.dumps(msg))

    def neuro_unregister_all_actions():
        if len(_neuro_registered_actions) == 0:
            return
        renpy.log("[NEURO] Unregistering all actions")
        msg = {
            "command": "actions/unregister",
            "game": _neuro_get_game_name(),
            "data": {
                "action_names": [action["name"] for action in _neuro_registered_actions]
            }
        }
        _neuro_send_ws_message(json.dumps(msg))

    def neuro_force_action(action_names, query):
        renpy.log("[NEURO] Forcing actions: {}".format(action_names))
        filtered_action_names = list(filter(lambda name: any(action["name"] == name for action in _neuro_registered_actions), action_names))
        if len(filtered_action_names) == 0:
            renpy.log("[NEURO] None of the specified actions are registered, skipping force action.")
            return
        msg = {
            "command": "actions/force",
            "game": _neuro_get_game_name(),
            "data": {
                "query": query,
                "action_names": list(filtered_action_names)
            }
        }
        _neuro_send_ws_message(json.dumps(msg))

    def _neuro_handle_progress_dialogue_action(data):
        _neuro_call_func_after_voiceover(renpy.exports.queue_event, "dismiss")
        return (True, "Progressing dialogue.")

    def _neuro_handle_skip_action(data):
        renpy.run(Skip())
        neuro_unregister_action("skip")
        return (True, "Skipping dialogue.")

    def _neuro_handle_continue_action(data):
        renpy.exports.queue_event("dismiss")
        return (True, "Continuing the game.")

    def _neuro_handle_select_option_action(data):
        success = True
        message = ""
        try:
            option = data.get("option")
            choice = next((c for c in _neuro_menu_choices if _neuro_clean_str(c[0]) == option), None)
            if option is None:
                success = False
                message = "ERROR: No option selected."
            elif choice is None:
                success = False
                choices_str = ", ".join(['"' + _neuro_clean_str(c[0]) + '"' for c in _neuro_menu_choices])
                message = "ERROR: Option '{}' is not valid. Please select one of the available options: {}.".format(option, choices_str)
            else:
                message = "You selected the option: {}".format(option)
                renpy.notify("Selected: \"" + option + "\"")
                _neuro_ensure_show_screen("_neuro_return_screen", choice[2])
        except Exception as e:
            success = False
            message = "ERROR: An error occurred while selecting the option: {}".format(str(e))
        return (success, message)

    def _neuro_handle_input_action(data):
        success = True
        message = ""
        user_input = data.get("input")
        if user_input is None:
            success = False
            message = "ERROR: No input provided."
        else:
            message = "You provided the input: {}".format(user_input)
            renpy.notify("Input: \"" + user_input + "\"")
            _neuro_ensure_show_screen("_neuro_return_screen", user_input)
        return (success, message)

    def _neuro_click_button(button_txt):
        global _neuro_ui_buttons
        button = next((b for b in _neuro_ui_buttons if _neuro_get_displayable_text(b) == button_txt), None)
        actions = button.action
        if button.action is None:
            actions = button.clicked
        if not isinstance(actions, (list, tuple)):
            actions = [actions]
        for action in actions:
            if action.__class__.__name__ == "Return":
                value = getattr(action, "value", None)
                _neuro_ensure_show_screen("_neuro_return_screen", value)
                _neuro_ui_buttons = []
                continue
            if action.__class__.__name__ == "ChoiceReturn":
                value = getattr(action, "value", None)
                _neuro_ensure_show_screen("_neuro_return_screen", value)
                _neuro_ui_buttons = []
                continue
            if action.__class__.__name__ == "Curry":
                fn = getattr(action, "callable", None)
                if getattr(fn, "__name__", None) == "_returns":
                    _neuro_ensure_show_screen("_neuro_return_screen", action.args[0])
                    _neuro_ui_buttons = []
                    continue
            if action.__class__.__name__ == "Function":
                action.function(*action.args, **action.kwargs)
                continue
            #renpy.log(action.__class__.__name__)
            action()
        renpy.restart_interaction()
        neuro_unregister_action("click_button")

    def _neuro_handle_click_button_action(data):
        success = True
        message = ""
        button_txt = data.get("button")
        button = next((b for b in _neuro_ui_buttons if _neuro_get_displayable_text(b) == button_txt), None)
        if button_txt is None:
            success = False
            message = "ERROR: No button selected."
        elif button is None:
            success = False
            buttons_str = ", ".join([_neuro_get_displayable_text(b) for b in _neuro_ui_buttons])
            message = "ERROR: Button '{}' is not valid. Please select one of the available buttons: {}.".format(button_txt, buttons_str)
        else:
            message = "You clicked the button: {}".format(button_txt)
            renpy.notify("Clicked: \"" + button_txt + "\"")
            _neuro_delayed_function(
                0.1,
                _neuro_click_button,
                button_txt
            )
        return (success, message)

    neuro_action_handlers = {
        "progress_dialogue": _neuro_handle_progress_dialogue_action,
        "skip": _neuro_handle_skip_action,
        "continue": _neuro_handle_continue_action,
        "select_option": _neuro_handle_select_option_action,
        "input": _neuro_handle_input_action,
        "click_button": _neuro_handle_click_button_action
    }

    def _neuro_handle_action(action_id, action_name, action_json_str):
        renpy.log("[NEURO] Handling action: {} (ID: {})".format(action_name, action_id))
        renpy.log("[NEURO] Action data: {}".format(action_json_str))

        if action_json_str:
            action_json = json.loads(action_json_str)
        else:
            action_json = {}

        success = True
        message = ""

        try:
            success, message = neuro_action_handlers[action_name](action_json)
        except KeyError:
            success = False
            message = "ERROR: Action '{}' is not registered or not supported.".format(action_name)
        except Exception as e:
            success = False
            message = "ERROR: An error occurred while processing the action: {}".format(str(e))

        msg = {
            "command": "action/result",
            "game": _neuro_get_game_name(),
            "data": {
                "id": action_id,
                "success": success,
                "message": message
            }
        }
        _neuro_send_ws_message(json.dumps(msg))


    ### WEBSOCKET CONNECTION ###

    def _neuro_send_ws_message(message, ws=None):
        if ws is None:
            ws = _neuro_ws
        if ws and ws.sock and ws.sock.connected:
            ws.send(message)
            return True
        else:
            return False

    def _neuro_ws_on_open(ws):
        renpy.log("[NEURO] WebSocket connection opened")

        # Send initial message to the server
        msg = {
            "command": "startup",
            "game": _neuro_get_game_name(),
        }
        _neuro_send_ws_message(json.dumps(msg), ws)

        # Give initial context of the game
        neuro_give_context("You are now playing the visual novel '{}'.".format(_neuro_get_game_name()), silent=False)

        # Register all currently registered actions
        if len(_neuro_registered_actions) > 0:
            msg = {
                "command": "actions/register",
                "game": _neuro_get_game_name(),
                "data": {
                    "actions": _neuro_registered_actions
                }
            }
            _neuro_send_ws_message(json.dumps(msg), ws)

    def _neuro_ws_on_message(ws, message):
        renpy.log("[NEURO] Message received: " + message)

        data = json.loads(message)
        if data.get("command") == "action":
            _neuro_handle_action(data.get("data").get("id"), data.get("data").get("name"), data.get("data").get("data"))
        elif data.get("command") == "actions/reregister_all":
            renpy.log("[NEURO] Re-registering all actions")
            msg = {
                "command": "actions/register",
                "game": _neuro_get_game_name(),
                "data": {
                    "actions": _neuro_registered_actions
                }
            }
            _neuro_send_ws_message(json.dumps(msg), ws)
        elif data.get("command") == "shutdown/graceful":
            # Go to the main menu when dialogue is done
            renpy.log("[NEURO] Received shutdown command, will leave the game at the next opportunity.")
            persistent._neuro_shutdown_requested = data.get("data", {}).get("wants_shutdown", True)
        elif data.get("command") == "shutdown/immediate":
            # Immediately go to the main menu
            _neuro_leave_game(True)
    def _neuro_ws_on_error(ws, error):
        renpy.log("[NEURO] Error occurred:", error)

    def _neuro_ws_on_close(ws, close_status_code, close_msg):
        renpy.log("[NEURO] WebSocket connection closed:", close_status_code, close_msg)

    def _neuro_ws_run():
        global _neuro_ws
        try:
            while True:
                _neuro_ws = websocket.WebSocketApp(
                    neuro_get_config("ws_url"),
                    on_open=_neuro_ws_on_open,
                    on_message=_neuro_ws_on_message,
                    on_error=_neuro_ws_on_error,
                    on_close=_neuro_ws_on_close
                )
                _neuro_ws.run_forever()
                time.sleep(1) # Wait before trying to reconnect
        except Exception as e:
            renpy.log("[NEURO] Exception in WebSocket thread: {}".format(str(e)))
    renpy.invoke_in_thread(_neuro_ws_run)


    ### REGISTER ACTION AND TIMEOUT FUNCTIONS ###

    # Function to register the progress_dialogue action
    def _neuro_register_progress_dialogue_action_and_deadline():
        neuro_register_action(
            "progress_dialogue",
            "Progress the dialogue.",
            {}
        )
        _neuro_delayed_function(
            neuro_get_config("max_progression_time") - neuro_get_config("min_progression_time"),
            neuro_force_action,
            ["progress_dialogue"] + (["skip"] if _neuro_can_skip() else []),
            "Please progress the dialogue using the progress_dialogue action.",
        )

    # Function to register the continue action
    def _neuro_register_continue_action_and_deadline():
        neuro_register_action(
            "continue",
            "Continue the game.",
            {}
        )
        _neuro_delayed_function(
            neuro_get_config("max_interaction_time") - neuro_get_config("min_interaction_time"),
            neuro_force_action,
            ["continue"],
            "Please continue the game using the continue action.",
        )

    # Function to register the select_option action
    def _neuro_register_select_option_action_and_deadline(choices):
        neuro_register_action(
            "select_option",
            "Select an option from the menu.",
            {
                "type": "object",
                "properties": {
                    "option": {
                        "type": "string",
                        "enum": [_neuro_clean_str(choice[0]) for choice in choices],
                    }
                },
                "required": ["option"]
            }
        )
        _neuro_delayed_function(
            neuro_get_config("max_interaction_time") - neuro_get_config("min_interaction_time"),
            neuro_force_action,
            ["select_option"],
            "Please select an option using the select_option action.",
        )

    # Function to register the input action
    def _neuro_register_input_action_and_deadline(prompt, default=None):
        neuro_register_action(
            "input",
            "Provide input for the prompt: '{}'.".format(prompt) \
            + (" The default input is '{}'.".format(default) if default else ""),
            {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                    }
                },
                "required": ["input"]
            }
        )
        _neuro_delayed_function(
            neuro_get_config("max_interaction_time") - neuro_get_config("min_interaction_time"),
            neuro_force_action,
            ["input"],
            "Please provide input using the input action.",
        )

    # Function to register the click_button action
    def _neuro_register_click_button_action_and_deadline():
        neuro_register_action(
            "click_button",
            "Click a button on the screen.",
            {
                "type": "object",
                "properties": {
                    "button": {
                        "type": "string",
                        "enum": [_neuro_get_displayable_text(button) for button in _neuro_ui_buttons],
                    }
                },
                "required": ["button"]
            }
        )
        _neuro_delayed_function(
            neuro_get_config("max_interaction_time") - neuro_get_config("min_interaction_time"),
            neuro_force_action,
            ["click_button"],
            "Please click a button using the click_button action.",
        )


    ### REN'PY OVERWRITES ###

    # Register the label callback
    def _neuro_on_label(name, jumped):
        # Hide all delayed function screens when a label is jumped to
        # This is to ensure that the delayed function screen does not keep on running on menus
        _neuro_cancel_delayed_functions()
        if "main_menu" in name:
            if not persistent._neuro_shutdown_requested:
                if persistent._neuro_game_started:
                    # Game has just ended, start a new game or close the game window depending on the game_over_action config
                    if neuro_get_config("game_over_action") == "new_game":
                        neuro_give_context("The game is over. Starting a new game.", silent=True)
                        _neuro_delayed_function(
                            5.0,
                            _neuro_load,
                            True
                        )
                    elif neuro_get_config("game_over_action") == "close":
                        neuro_give_context("The game is over. Closing the game window.", silent=True)
                        _neuro_delayed_function(
                            5.0,
                            renpy.quit
                        )
                else:
                    # Auto-start the game if the main menu is loaded and auto_start is enabled
                    if neuro_get_config("auto_start"):
                        _neuro_delayed_function(
                            5.0,
                            _neuro_await_ws_connected,
                            _neuro_load,
                        )
            
        # Set the game started flag if the label is "start"
        if name == "start":
            persistent._neuro_game_started = True
    try:
        config.label_callbacks.append(_neuro_on_label)
    except:
        # Older Ren'Py versions may not have label_callbacks but use config.label_callback instead
        def new_label_callback(old_func, name, jumped):
            if old_func is not None:
                old_func(name, jumped)
            _neuro_on_label(name, jumped)
        _neuro_override_func(config, "label_callback", new_label_callback)

    # Register the after load callback
    def _neuro_after_load():
        persistent._neuro_game_started = True
    config.after_load_callbacks.append(_neuro_after_load)

    # Overwrite the default say function
    def _neuro_custom_say(old_func, who, what, interact=True, *args, **kwargs):
        _neuro_cancel_delayed_functions()

        if not renpy.config.skipping and what:
            _neuro_save()

            neuro_unregister_action("progress_dialogue")
            neuro_unregister_action("skip")
            neuro_unregister_action("continue")
            neuro_unregister_action("select_option")
            neuro_unregister_action("click_button")
            neuro_unregister_action("input")

            global _neuro_ui_buttons
            _neuro_ui_buttons = []

            neuro_give_context(_neuro_who_to_str(who) + ": " + _neuro_clean_str(what), silent=neuro_get_config("silent_dialogue"))

            # Allow skipping
            if _neuro_can_skip():
                neuro_register_action(
                    "skip",
                    "You have already seen this dialogue, you can skip it using this action.",
                    {}
                )

        if persistent._neuro_shutdown_requested:
            _neuro_delayed_function(
                3.0,
                _neuro_leave_game
            )

        # Progression
        if neuro_get_config("progression_mode") == "action":
            _neuro_delayed_function(
                neuro_get_config("min_progression_time"),
                _neuro_register_progress_dialogue_action_and_deadline
            )
        elif neuro_get_config("progression_mode") == "auto":
            _neuro_delayed_function(
                neuro_get_config("max_progression_time"),
                _neuro_call_func_after_voiceover,
                _neuro_await_ws_connected,
                renpy.exports.queue_event,
                "dismiss",
            )

        return old_func(who, what, interact, *args, **kwargs)
    _neuro_override_func(renpy.exports, "say", _neuro_custom_say)

    # Overwrite the default menu function
    def _neuro_custom_menu(old_func, items, *args, **kwargs):
        global _neuro_menu_choices
        _neuro_menu_choices = list(filter(lambda choice: r.python.py_eval(choice[1]), items))

        neuro_unregister_action("progress_dialogue")
        neuro_unregister_action("skip")

        if neuro_get_config("allow_interaction"):
            _neuro_delayed_function(
                neuro_get_config("min_interaction_time"),
                _neuro_register_select_option_action_and_deadline,
                _neuro_menu_choices
            )

        neuro_give_context("A menu appears with the following choices: " + ", ".join(["\"" + _neuro_clean_str(choice[0]) + "\"" for choice in _neuro_menu_choices]) + "." \
            + (" You must choose one using the select_option action once it appears." if neuro_get_config("allow_interaction") else ""),
            silent=neuro_get_config("silent_choices"))
        
        rv = old_func(items, *args, **kwargs)
        neuro_unregister_action("select_option")

        return rv
    _neuro_override_func(renpy.exports, "menu", _neuro_custom_menu)

    # Overwrite the default input function
    def _neuro_custom_input(old_func, prompt, default="", *args, **kwargs):
        prompt_sub = _neuro_clean_str(prompt)

        _neuro_cancel_delayed_functions()

        neuro_unregister_action("progress_dialogue")
        neuro_unregister_action("skip")
        neuro_unregister_action("continue")
        neuro_unregister_action("select_option")
        neuro_unregister_action("click_button")
        neuro_unregister_action("input")

        if neuro_get_config("allow_interaction"):
            _neuro_delayed_function(
                neuro_get_config("min_interaction_time"),
                _neuro_register_input_action_and_deadline,
                prompt_sub,
                default,
            )

        neuro_give_context("An input prompt appears with the following message: '{}'.".format(prompt_sub) \
            + (" The default input is '{}'.".format(default) if default else "") \
            + (" You must provide input using the input action once it appears." if neuro_get_config("allow_interaction") else ""),
            silent=neuro_get_config("silent_choices"))

        rv = old_func(prompt, default, *args, **kwargs)
        neuro_unregister_action("input")

        return rv
    _neuro_override_func(renpy.exports, "input", _neuro_custom_input)

    # Overwrite the default show screen function to catch custom menus, modals, etc.
    def _neuro_handle_screen(screen_name):
        try:
            screen = renpy.exports.get_screen(screen_name)
            if screen is None:
                renpy.log("[NEURO] Screen '{}' not found.".format(screen_name))
                return
            buttons = _neuro_find_buttons_in_displayble(screen)
            if neuro_get_config("allow_interaction") and len(buttons) > 0:
                global _neuro_ui_buttons
                _neuro_ui_buttons = buttons
                _neuro_delayed_function(
                    neuro_get_config("min_interaction_time"),
                    _neuro_register_click_button_action_and_deadline
                )
            neuro_give_context(
                "A {} screen appears with the following content:\n\"{}\"".format(screen_name, _neuro_get_displayable_text(screen)) \
                + ("\nYou must interact with the screen using the actions provided to you once they appear." if neuro_get_config("allow_interaction") and len(buttons) > 0 else ""),
                silent=neuro_get_config("silent_choices")
            )
        except Exception as e:
            renpy.log("[NEURO] Error handling screen '{}': {}".format(screen_name, str(e)))
    def _neuro_custom_show_screen(old_func, screen_name, *args, **kwargs):
        old_func(screen_name, *args, **kwargs)
        if screen_name.startswith("_neuro"):
            return
        if screen_name in DEFAULT_RENPY_SCREENS:
            return

        neuro_unregister_action("progress_dialogue")
        neuro_unregister_action("skip")

        _neuro_delayed_function(
            0.1,
            _neuro_handle_screen,
            screen_name
        )
    _neuro_override_func(renpy.exports, "show_screen", _neuro_custom_show_screen)

    # Overwrite the default ui.button function to catch buttons created in code
    def _neuro_custom_ui_button(old_func, *args, **kwargs):
        button = old_func(*args, **kwargs)
        if neuro_get_config("allow_interaction"):
            global _neuro_ui_buttons
            try:
                _neuro_ui_buttons.append(button)
            except:
                _neuro_ui_buttons = [button]
        return button
    _neuro_override_func(renpy.ui, "button", _neuro_custom_ui_button)

    # Overwrite the default ui.textbutton function to catch text buttons created in code
    def _neuro_custom_ui_textbutton(old_func, *args, **kwargs):
        button = renpy.display.behavior.Button(**kwargs)
        text = renpy.text.text.Text(args[0])
        button.add(text)
        if neuro_get_config("allow_interaction"):
            global _neuro_ui_buttons
            try:
                _neuro_ui_buttons.append(button)
            except:
                _neuro_ui_buttons = [button]
        return old_func(*args, **kwargs)
    _neuro_override_func(renpy.ui, "textbutton", _neuro_custom_ui_textbutton)

    # Overwrite the default ui.imagebutton function to catch image buttons created in code
    def _neuro_custom_ui_imagebutton(old_func, *args, **kwargs):
        button = old_func(*args, **kwargs)
        if neuro_get_config("allow_interaction"):
            global _neuro_ui_buttons
            try:
                _neuro_ui_buttons.append(button)
            except:
                _neuro_ui_buttons = [button]
        return button
    _neuro_override_func(renpy.ui, "imagebutton", _neuro_custom_ui_imagebutton)

    # Overwrite the default ui.interact function to catch whenever the game expects user interaction
    def _neuro_custom_ui_interact(old_func, *args, **kwargs):
        global _neuro_ui_buttons
        if '_neuro_ui_buttons' in globals() and len(_neuro_ui_buttons) > 0:
            # There are buttons available to interact with
            _neuro_cancel_delayed_functions()
            neuro_unregister_action("progress_dialogue")
            neuro_unregister_action("skip")
            if neuro_get_config("allow_interaction"):
                _neuro_delayed_function(
                    neuro_get_config("min_interaction_time"),
                    _neuro_register_click_button_action_and_deadline
                )
        elif "type" in kwargs and kwargs["type"] == "pause":
            # The game is paused, allow continuing
            _neuro_cancel_delayed_functions()
            neuro_unregister_action("progress_dialogue")
            neuro_unregister_action("skip")
            if neuro_get_config("allow_interaction"):
                _neuro_delayed_function(
                    neuro_get_config("min_interaction_time"),
                    _neuro_register_continue_action_and_deadline
                )
        rv = old_func(*args, **kwargs)
        if not renpy.config.skipping:
            neuro_unregister_action("click_button")
        return rv
    _neuro_override_func(renpy.ui, "interact", _neuro_custom_ui_interact)


screen _neuro_delayed_function_screen_0(delay, function, args, kwargs):
    zorder 1000
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 0), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_1(delay, function, args, kwargs):
    zorder 1001
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 1), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_2(delay, function, args, kwargs):
    zorder 1002
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 2), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_3(delay, function, args, kwargs):
    zorder 1003
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 3), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_4(delay, function, args, kwargs):
    zorder 1004
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 4), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_5(delay, function, args, kwargs):
    zorder 1005
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 5), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_6(delay, function, args, kwargs):
    zorder 1006
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 6), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_7(delay, function, args, kwargs):
    zorder 1007
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 7), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_8(delay, function, args, kwargs):
    zorder 1008
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 8), Function(function, *args, **kwargs)]

screen _neuro_delayed_function_screen_9(delay, function, args, kwargs):
    zorder 1009
    modal False
    timer delay action [Function(_neuro_cancel_delayed_function, 9), Function(function, *args, **kwargs)]

screen _neuro_return_screen(value):
    zorder 2000
    modal False
    timer 0.1 action [Hide("_neuro_return_screen"), Return(value)]