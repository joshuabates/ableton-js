def is_jsonable(x):
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False


class Interface(object):
    obj_ids = dict()
    listeners = dict()

    @staticmethod
    def save_obj(obj):
        obj_id = id(obj)
        Interface.obj_ids[obj_id] = obj
        return obj_id

    @staticmethod
    def get_obj(obj_id):
        return Interface.obj_ids[obj_id]

    def __init__(self, c_instance, socket):
        self.ableton = c_instance
        self.socket = socket
        self.log_message = c_instance.log_message

    def get_ns(self, nsid):
        return Interface.obj_ids[nsid]

    def handle(self, payload):
        name = payload.get("name")
        uuid = payload.get("uuid")
        args = payload.get("args", {})
        ns = self.get_ns(payload.get("nsid"))

        try:
            # Try self-defined functions first
            if hasattr(self, name) and callable(getattr(self, name)):
                result = getattr(self, name)(ns=ns, **args)
                self.socket.send("result", result, uuid)
            # Check if the function exists in the Ableton API as fallback
            elif hasattr(ns, name) and callable(getattr(ns, name)):
                if isinstance(args, dict):
                    result = getattr(ns, name)(**args)
                    self.socket.send("result", result, uuid)
                elif isinstance(args, list):
                    result = getattr(ns, name)(*args)
                    self.socket.send("result", result, uuid)
                else:
                    self.socket.send("error", "Function call failed: " + str(args) +
                                     " are invalid arguments", uuid)
            else:
                self.socket.send("error", "Function call failed: " + payload["name"] +
                                 " doesn't exist or isn't callable", uuid)
        except Exception, e:
            self.socket.send("error", str(e.args[0]), uuid)

    def add_listener(self, ns, prop, eventId, nsid="Default"):
        try:
            add_fn = getattr(ns, "add_" + prop + "_listener")
        except:
            raise Exception("Listener " + str(prop) + " does not exist.")

        key = str(nsid) + prop
        self.log_message("Add key: " + key)
        if self.listeners.has_key(key):
            return self.listeners[key]["id"]

        def fn():
            return self.socket.send(eventId, self.get_prop(ns, prop))

        add_fn(fn)
        self.listeners[key] = {"id": eventId, "fn": fn}
        return eventId

    def remove_listener(self, ns, prop, nsid="Default"):
        key = str(nsid) + prop
        self.log_message("Remove key: " + key)
        if not self.listeners.has_key(key):
            raise Exception("Listener " + str(prop) + " does not exist.")

        try:
            remove_fn = getattr(ns, "remove_" + prop + "_listener")
            remove_fn(self.listeners[key]["fn"])
            self.listeners.pop(key, None)
            return True
        except Exception as e:
            raise Exception("Listener " + str(prop) +
                            " could not be removed: " + str(e))

    def get_prop(self, ns, prop):
        try:
            get_fn = getattr(self, "get_" + prop)
        except:
            def get_fn(ns):
                result = getattr(ns, prop)
                return result if is_jsonable(result) else str(result)

        return get_fn(ns)

    def set_prop(self, ns, prop, value):
        try:
            set_fn = getattr(self, "set_" + prop)
        except:
            def set_fn(ns, value): return setattr(ns, prop, value)

        return set_fn(ns, value)
