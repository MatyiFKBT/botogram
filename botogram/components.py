"""
    botogram.components
    Definition of the components system

    Copyright (c) 2015 Pietro Albini
    Released under the MIT license
"""

import re
import functools

from . import utils


class Component:
    """A component of a bot"""

    component_name = None

    def __init__(self, name=None):
        # These will contain all the things registered in this component
        self.__commands = {}
        self.__processors = []
        self.__before_processors = []

        # Be sure to have a component name
        if name is not None:
            self.component_name = name
        elif self.component_name is None:
            self.component_name = self.__class__.__name__

    def add_before_processing_hook(self, func):
        """Register a before processing hook"""
        if not callable(func):
            raise ValueError("A before processing hook must be callable")

        self.__before_processors.append(func)

    def add_process_message_hook(self, func):
        """Add a message processor hook"""
        if not callable(func):
            raise ValueError("A message processor must be callable")

        self.__processors.append(func)

    def add_message_contains_hook(self, func, string, ignore_case=True,
                                  multiple=False):
        """Add a message contains hook"""
        if not callable(func):
            raise ValueError("A message contains hook must be callable")

        regex = r'\b('+string+r')\b'
        flags = re.IGNORECASE if ignore_case else 0

        @functools.wraps(func)
        @utils.pass_bot
        def wrapped(bot, chat, message, matches):
            return bot._call(func, chat, message)

        self.add_message_matches_hook(wrapped, regex, flags, multiple)

    def add_message_matches_hook(self, func, regex, flags=0, multiple=False):
        """Apply a message matches hook"""
        if not callable(func):
            raise ValueError("A message matches hook must be callable")

        @functools.wraps(func)
        @utils.pass_bot
        def processor(bot, chat, message):
            if message.text is None:
                return

            compiled = re.compile(regex, flags=flags)
            results = compiled.finditer(message.text)

            found = False
            for result in results:
                found = True

                bot._call(func, chat, message, result.groups())
                if not multiple:
                    break

            return found

        self.__processors.append(processor)

    def add_command(self, func, name):
        """Register a new command"""
        if name in self.__commands:
            raise NameError("The command /%s already exists" % name)

        if not callable(func):
            raise ValueError("A command processor must be callable")

        self.__commands[name] = func

    def _get_hooks_chain(self):
        """Get the full hooks chain for this component"""
        chain = [
            self.__before_processors,
            self.__generate_commands_processors(),
            self.__processors,
        ]
        return [[self.__wrap_function(f) for f in c] for c in chain]

    def _get_commands(self):
        """Get all the commands this component implements"""
        return self.__commands

    def __generate_commands_processors(self):
        """Generate a list of commands processors"""
        def base(name, func):
            @functools.wraps(func)
            @utils.pass_bot
            def __(bot, chat, message):
                # Commands must have a message
                if message.text is None:
                    return

                # Must be this command
                match = bot._commands_re.match(message.text)
                if not match or match.group(1) != name:
                    return

                args = message.text.split(" ")[1:]
                bot._call(func, chat, message, args)
                return True
            return __

        return [base(name, func) for name, func in self.__commands.items()]

    def __wrap_function(self, func):
        """Wrap a function, adding to it component-specific things"""
        if not hasattr(func, "botogram"):
            func.botogram = HookDetails()

        prefix = self.component_name+"::" if self.component_name else ""

        func.botogram.name = prefix+func.__name__
        func.botogram.component = self

        return func


class HookDetails:
    """Container for some details of user-provided hooks"""

    def __init__(self):
        self.name = ""
        self.component = None
