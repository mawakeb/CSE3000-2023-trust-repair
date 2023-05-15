import warnings
import copy
import numpy as np
from matrx.grid_world import AgentBody
from matrx.agents import AgentBrain, HumanAgentBrain, SenseCapability
from matrx.actions.object_actions import GrabObject, DropObject, RemoveObject
from matrx.actions.door_actions import OpenDoorAction, CloseDoorAction
from matrx.agents.agent_utils.state import State
from matrx.agents.agent_utils.state_tracker import StateTracker
from matrx.agents import HumanAgentBrain
from matrx.messages import Message
from matrx.objects import EnvObject
from matrx.actions.move_actions import MoveNorth, MoveNorthEast, MoveEast, MoveSouthEast, MoveSouth, MoveSouthWest, \
    MoveWest, MoveNorthWest
from actions1.CustomActions import RemoveObjectTogether, Idle, CarryObject, CarryObjectTogether, DropObjectTogether, \
    Drop, RemoveObject, AddObject


class HumanBrain(HumanAgentBrain):
    """ Creates an Human Agent which is an agent that can be controlled by a human.
    """

    def __init__(self, memorize_for_ticks=None, fov_occlusion=False, max_carry_objects=1, grab_range=1, drop_range=1,
                 door_range=1, remove_range=1, condition='baseline'):
        super().__init__(memorize_for_ticks=memorize_for_ticks)
        self.__fov_occlusion = fov_occlusion
        if fov_occlusion:
            warnings.warn("FOV Occlusion is not yet fully implemented. "
                          "Setting fov_occlusion to True has no effect.")
        self.__max_carry_objects = max_carry_objects
        self.__remove_range = remove_range
        self.__grab_range = grab_range
        self.__drop_range = drop_range
        self.__door_range = door_range
        self.__remove_range = remove_range
        self.__condition = condition

    def _factory_initialise(self, agent_name, agent_id, action_set,
                            sense_capability, agent_properties,
                            customizable_properties, rnd_seed,
                            callback_is_action_possible, key_action_map=None):
        """ Called by the WorldFactory to initialise this agent with all
        required properties in addition with any custom properties.

        This also sets the random number generator with a seed generated based o
        n the random seed of the
        world that is generated.

        Note; This method should NOT be overridden!

        Parameters
        ----------
        agent_name : str
            The name of the agent.
        agent_id: str
            The unique ID given by the world to this agent's avatar. So the
            agent knows what body is his.
        action_set : List
            The list of action names this agent is allowed to perform.
        sense_capability : SenseCapability
            The SenseCapability of the agent denoting what it can see withing
            what range.
        agent_properties : dict
            The dictionary of properties containing all mandatory and custom
            properties.
        customizable_properties : list
            A list of keys in agent_properties that this agent is allowed to
            change.
        rnd_seed : int
            The random seed used to set the random number generator self.rng
        key_action_map : (optional, default, None)
            Maps user pressed keys (e.g. arrow key up) to a specific action.
            See this link for the available keys
            https://developer.mozilla.org/nl/docs/Web/API/KeyboardEvent/key/Key_Values
        """

        # The name of the agent with which it is also known in the world
        self.agent_name = agent_name
        self.image = "/images/rescue-man-final3.svg"

        # The id of the agent
        self.agent_id = agent_id

        # The names of the actions this agent is allowed to perform
        self.action_set = action_set

        # Setting the random seed and rng
        self.rnd_seed = rnd_seed
        self._set_rnd_seed(seed=rnd_seed)

        # The SenseCapability of the agent; what it can see and within what
        # range
        self.sense_capability = sense_capability

        # Contains the agent_properties
        self.agent_properties = agent_properties

        # Specifies the keys of properties in self.agent_properties which can
        # be changed by this Agent in this file. If it is not writable, it can
        # only be  updated through performing an action which updates that
        # property (done by the environment).
        # NOTE: Changing which properties are writable cannot be done during
        #  runtime! Only in  the scenario manager
        self.keys_of_agent_writable_props = customizable_properties

        # A callback to the GridWorld instance that can check whether any
        # action (with its arguments) will succeed and
        # if not why not (in the form of an ActionResult).
        self.__callback_is_action_possible = callback_is_action_possible

        # a list which maps user inputs to actions, defined in the scenario
        # manager
        if key_action_map is None:
            self.key_action_map = {}
        else:
            self.key_action_map = key_action_map

        # Initializing the State object
        self._init_state()

    def _get_action(self, state, agent_properties, agent_id, user_input):
        """ The function the environment calls. The environment receives this
        function object and calls it when it is time for this agent to select
        an action.

        The function overwrites the default get_action() function for normal
        agents, and instead executes the action commanded by the user, which
        is received via the api from e.g. a visualization interface.

        Note; This method should NOT be overridden!

        Parameters
        ----------
        state : dict
            A state description containing all properties of EnvObject that
            are within a certain range as defined by self.sense_capability.
            It is a list of properties in a dictionary
        agent_properties : dict
            The properties of the agent, which might have been changed by the
            environment as a result of actions of this or other agents.
        agent_id : str
            the ID of this agent
        user_input : list
            any user input given by the user for this human agent via the api

        Returns
        -------
         filtered_state : dict
            The filtered state of this agent
        agent_properties : dict
            the agent properties which the agent might have changed,
        action : str
            an action string, which is the class name of one of the actions in
            the Action package.
        action_kwargs : dict
            Keyword arguments for the action

        """
        # Process any properties of this agent which were updated in the
        # environment as a result of actions
        self.agent_properties = agent_properties

        # Update the state property of an agent with the GridWorld's state
        # dictionary
        self.state.state_update(state.as_dict())

        # Call the filter method to filter the observation
        self.state = self.filter_observations(self.state)

        # only keep user input which is actually connected to an agent action
        usrinput = self.filter_user_input(user_input)

        # Call the method that decides on an action
        action, action_kwargs = self.decide_on_action(self.state, usrinput)

        # Store the action so in the next call the agent still knows what it
        # did.
        self.previous_action = action

        # Return the filtered state, the (updated) properties, the intended
        # actions and any keyword arguments for that action if needed.
        return self.state, self.agent_properties, action, action_kwargs

    def decide_on_action(self, state, user_input):
        """ Contains the decision logic of the agent.

        This method determines what action the human agent will perform. The
        GridWorld is responsible for deciding when an agent can perform an
        action again, if so this method is called for each agent. Two things
        need to be determined, which action and with what arguments.

        The action is returned simply as the class name (as a string), and the
         action arguments as a dictionary with the keys the names of the
         keyword arguments. An argument that is always possible is that of
         action_duration, which denotes how many ticks this action should take
         (e.g. a duration of 1, makes sure the agent has to wait 1 tick).

        Note; this function of the human_agent_brain overwrites the
          decide_on_action() function of the default agent, also providing the
          user input.


        Parameters
        ==========
        state : State
            A state description containing all properties of EnvObject that
            are within a certain range as defined by self.sense_capability.

        user_input : list
            A dictionary containing the key presses of the user, intended for
            controlling thus human agent.

        Returns
        =============
        action_name : str
            A string of the class name of an action that is also in
            self.action_set. To ensure backwards compatibility you could use
            Action.__name__ where Action is the intended action.

        action_args : dict
            A dictionary with keys any action arguments and as values the
            actual argument values. If a required argument is missing an
            exception is raised, if an argument that is not used by that
            action a warning is printed. The argument applicable to all action
            is `action_duration`, which sets the number ticks the agent is put
            on hold by the GridWorld until the action's world mutation is
            actual performed and the agent can perform a new action (a value
            of 0 is no wait, 1 means to wait 1 tick, etc.).
        """
        self._tick = state['World']['nr_ticks']
        action = None
        action_kwargs = {}
        area_tiles = [(2, 2), (2, 3), (3, 2), (3, 3), (4, 2), (4, 3), (8, 2), (8, 3), (9, 2), (9, 3), (10, 2), (10, 3), (14, 2), (14, 3), (15, 2), (15, 3), (16, 2), (16, 3), (20, 2), (20, 3),
                (21, 2), (21, 3), (22, 2), (22, 3), (2, 8), (2, 9), (3, 8), (3, 9), (4, 8), (4, 9), (8, 8), (8, 9), (9, 8), (9, 9), (10, 8), (10, 9), (14, 8), (14, 9), (15, 8), (15, 9),
                (16, 8), (16, 9), (2, 14), (2, 15), (3, 14), (3, 15), (4, 14), (4, 15), (8, 14), (8, 15), (9, 14), (9, 15), (10, 14), (10, 15), (14, 14), (14, 15), (15, 14), (15, 15), (16, 14),
                (16, 15), (2, 20), (2, 21), (3, 20), (3, 21), (4, 20), (4, 21), (8, 20), (8, 21), (9, 20), (9, 21), (10, 20), (10, 21), (14, 20), (14, 21), (15, 20), (15, 21), (16, 20), 
                (16, 21), (20, 20), (20, 21), (21, 20), (21, 21), (22, 20), (22, 21), (23, 8), (23, 9), (23, 10), (23, 11), (23, 12), (23, 13), (23, 14), (23, 15),
                (3, 4), (9, 4), (15, 4), (21, 4), (3, 7), (9, 7), (15, 7), (3, 16), (9, 16), (15, 16), (3, 19), (9, 19), (15, 19), (21, 19)]

        for info in state.values():
            if 'class_inheritance' in info and 'AreaTile' in info['class_inheritance'] and info['location'] not in area_tiles:
                area_tiles.append(info['location'])

        if self.__condition != 'tutorial':
            if self._tick == 1200 or self._tick == 2400 or self._tick == 3600:
                self.image = self.agent_properties["img_name"]

            if state[{"name": 'human'}]['location'] in area_tiles and self._tick > 1200 and self._tick < 1300 or \
                    state[{"name": 'human'}]['location'] in area_tiles and self._tick > 2400 and self._tick < 2500 or \
                    state[{"name": 'human'}]['location'] in area_tiles and self._tick > 3600 and self._tick < 3700:
                self.image = self.agent_properties["img_name"]

            if state[{"name": 'human'}]['location'] not in area_tiles and self._tick > 1200 and self._tick < 1300 or \
                    state[{"name": 'human'}][
                        'location'] not in area_tiles and self._tick > 2400 and self._tick < 2500 or \
                    state[{"name": 'human'}]['location'] not in area_tiles and self._tick > 3600 and self._tick < 3700:
                self.agent_properties["img_name"] = "/images/human-danger2.gif"
                self.agent_properties["visualize_size"] = 2
                return None, {}

            if self._tick == 1300:
                self.agent_properties["img_name"] = str(self.image)
                self.agent_properties["visualize_size"] = 1

            if self._tick == 2500:
                self.agent_properties["img_name"] = str(self.image)
                self.agent_properties["visualize_size"] = 1

            if self._tick == 3700:
                self.agent_properties["img_name"] = str(self.image)
                self.agent_properties["visualize_size"] = 1

        # if no keys were pressed, do nothing
        if user_input is None or user_input == []:
            return None, {}

        # take the latest pressed key (for now), and fetch the action
        # associated with that key
        pressed_keys = user_input[-1]
        action = self.key_action_map[pressed_keys]

        # if the user chose a grab together action, choose an object within grab_range
        if action == CarryObjectTogether.__name__:
            # Set grab range
            action_kwargs['grab_range'] = self.__grab_range
            # Set max amount of objects
            action_kwargs['max_objects'] = self.__max_carry_objects
            action_kwargs['condition'] = self.__condition

            # grab the closest victim
            obj_id = self.__select_random_obj_in_range(state,
                                                       range_=self.__grab_range,
                                                       property_to_check="is_movable")
            if obj_id and 'healthy' in obj_id:
                action_kwargs['object_id'] = obj_id
            if obj_id and 'mild' in obj_id:
                action_kwargs['object_id'] = obj_id
                action_kwargs['action_duration'] = 10
            if obj_id and 'critical' in obj_id:
                action_kwargs['object_id'] = obj_id
                if self.__condition != 'mixed':
                    action_kwargs['action_duration'] = 20

                # If the user chose to drop an object in its inventory
        elif action == DropObjectTogether.__name__:
            action_kwargs['drop_range'] = self.__drop_range
            action_kwargs['condition'] = self.__condition
            pass

        if action == CarryObject.__name__:
            # Assign it to the arguments list
            # Set grab range
            action_kwargs['grab_range'] = self.__grab_range
            # Set max amount of objects
            action_kwargs['max_objects'] = self.__max_carry_objects
            action_kwargs['object_id'] = None
            action_kwargs['condition'] = self.__condition

            obj_id = \
                self.__select_random_obj_in_range(state,
                                                  range_=self.__grab_range,
                                                  property_to_check="is_movable")
            if obj_id and 'healthy' in obj_id:
                action_kwargs['object_id'] = obj_id
            if obj_id and 'mild' in obj_id:
                action_kwargs['object_id'] = obj_id
                if self.__condition == 'mixed':
                    action_kwargs['action_duration'] = 10  # no-constraints: carried together does not improve time
                else:
                    action_kwargs['action_duration'] = 40
            if obj_id and 'critical' in obj_id:
                action_kwargs['object_id'] = obj_id
                if self.__condition == 'mixed':
                    action_kwargs['action_duration'] = 20  # independence: critical can only be rescued by human
                else:
                    action_kwargs['action_duration'] = 80

        # If the user chose to drop an object in its inventory
        elif action == Drop.__name__:
            # Assign it to the arguments list
            # Set drop range
            action_kwargs['drop_range'] = self.__drop_range
            action_kwargs['condition'] = self.__condition
            pass

        # If the user chose to remove an object
        elif action == RemoveObjectTogether.__name__:
            # Assign it to the arguments list
            # Set drop range
            action_kwargs['remove_range'] = self.__remove_range
            action_kwargs['condition'] = self.__condition
            action_kwargs['object_id'] = None

            obj_id = \
                self.__select_random_obj_in_range(state,
                                                  range_=self.__remove_range,
                                                  property_to_check="is_movable")
            if self.__condition != 'complementary':
                action_kwargs['object_id'] = obj_id
                if obj_id and 'stone' in obj_id:
                    action_kwargs['action_duration'] = 10
                if obj_id and 'rock' in obj_id:
                    action_kwargs['action_duration'] = 30
                if obj_id and 'tree' in obj_id:
                    action_kwargs['action_duration'] = 20
        
        # If the user chose to remove an object
        elif action == RemoveObject.__name__:
            # Assign it to the arguments list
            # Set drop range
            action_kwargs['remove_range'] = self.__remove_range
            action_kwargs['condition'] = self.__condition
            action_kwargs['object_id'] = None

            obj_id = \
                self.__select_random_obj_in_range(state,
                                                  range_=self.__remove_range,
                                                  property_to_check="is_movable")
            if self.__condition != 'complementary' and obj_id and 'critical' not in obj_id and 'mild' not in obj_id and 'healthy' not in obj_id:
                action_kwargs['object_id'] = obj_id
                if 'stone' in obj_id:
                    action_kwargs['action_duration'] = 40
                if 'rock' in obj_id:
                    action_kwargs['action_duration'] = 120
                if 'tree' in obj_id:
                    action_kwargs['action_duration'] = 80
   
        # if the user chose to do an open or close door action, find a door to
        # open/close within range
        elif action == OpenDoorAction.__name__ \
                or action == CloseDoorAction.__name__:
            action_kwargs['door_range'] = self.__door_range
            action_kwargs['object_id'] = None

            # Get all doors from the perceived objects
            objects = list(state.keys())
            doors = [obj for obj in objects if 'is_open' in state[obj]]

            # get all doors within range
            doors_in_range = []
            for object_id in doors:
                # Select range as just enough to grab that object
                dist = int(np.ceil(np.linalg.norm(
                    np.array(state[object_id]['location']) - np.array(
                        state[self.agent_id]['location']))))
                if dist <= action_kwargs['door_range']:
                    doors_in_range.append(object_id)

            # choose a random door within range
            if len(doors_in_range) > 0:
                action_kwargs['object_id'] = \
                    self.rnd_gen.choice(doors_in_range)

        elif action in [MoveNorth.__name__, MoveNorthEast.__name__, MoveEast.__name__, MoveSouthEast.__name__,
                        MoveSouth.__name__, MoveSouthWest.__name__, MoveWest.__name__, MoveNorthWest.__name__]:
            water_locs = []
            if state[{"name": "water"}]:
                for water in state[{"name": "water"}]:
                    if water['location'] not in water_locs:
                        water_locs.append(water['location'])
            if state[{"name": 'human'}]['location'] in water_locs and state[{"name": 'human'}]['location'] not in [
                (3, 5), (9, 5), (15, 5), (21, 5), (3, 6), (9, 6), (15, 6), (3, 17), (9, 17), (15, 17), (3, 18), (9, 18),
                (15, 18), (21, 18)]:
                action == Idle.__name__
                action_kwargs['duration_in_ticks'] = 2

        return action, action_kwargs

    def filter_observations(self, state):
        """
        All our agent work through the OODA-loop paradigm; first you
        observe, then you orient/pre-process, followed by a decision process
        of an action after which we act upon the action.

        However, as a human agent is controlled by a human, only the observe
        part is executed.

        This is the Observe phase. In this phase you filter the state
        further to only those properties the agent is actually SUPPOSED to
        see. Since the grid world returns ALL properties of ALL objects
        within a certain range(s), but perhaps some objects are obscured
        because they are behind walls, or an agent is not able to see some
        properties an certain objects.

        This filtering is what you do here.

        Parameters
        ----------
        state : dict
            A state description containing all properties of EnvObject that
            are within a certain range as defined by self.sense_capability.
            It is a list of properties in a dictionary

        Returns
        -------
         filtered_state : dict
            The filtered state of this agent

        """
        return state

    def filter_user_input(self, user_input):
        """ From the received userinput, only keep those which are actually
        connected to a specific agent action.

        Parameters
        ----------
        user_input : list
            A dictionary containing the key presses of the user, intended for
            controlling thus human agent.

        """

        # read messages and remove them
        for message in list(self.received_messages):
            self.received_messages.remove(message)

        if user_input is None:
            return []
        possible_key_presses = list(self.key_action_map.keys())
        return list(set(possible_key_presses) & set(user_input))

    def create_context_menu_for_self(self, clicked_object_id, click_location,
                                     self_selected):
        """ Generate options for a context menu for a specific object/location
        which the user controlling this human agent opened.

        For the default MATRX visualization, the context menu is opened by
        right clicking on an object. This function should generate a list of
        options (actions, messages, or something else) which relate to that
        object. Each option is in the shape of a text shown in the context
        menu, and a message which is send to this agent if the user actually
        clicks that context menu option.

        Parameters
        ----------
        clicked_object_id : str
            A string indicating the ID of an object. Is None if the user
            clicked on a background tile (which has no ID).
        click_location : list
            A list containing the [x,y] coordinates of the object on which the
            user right clicked.
        self_selected : bool
            Describes if the current human agent being controlled by the user
            was selected or not before opening the context menu. Depending on
            this, you might pass back a different context menu in this
            function. E.g. option 1: no-one selected + right click is the same
            as self selected + right click: both open the current agent's
            context menu. option 2: self selected + right click opens our own
            context menu, no one selected + right click gives a context menu
            with commands for the entire TEAM.

        Returns
        -------
         context_menu : list
            A list containing context menu items. Each context menu item is a
            dict with a 'OptionText' key, which is the text shown in the menu
            for the option, and a 'Message' key, which is the message instance
            that is sent to this agent when the user clicks on the context
            menu option.
        """
        print("Context menu self with self selected:", self_selected)

        context_menu = []

        for action in self.action_set:
            context_menu.append({
                "OptionText": f"Do action: {action}",
                "Message": Message(content=action, from_id=self.agent_id,
                                   to_id=self.agent_id)
            })

        return context_menu

    def create_context_menu_for_other(self, agent_id_who_clicked,
                                      clicked_object_id, click_location):
        """ Generate options for a context menu for a specific object/location
        that a user NOT controlling this human agent opened.

        Thus: another human agent selected this agent, opened a context menu
        by right clicking on an object or location. This function is called.

        It should return actions, messages, or other info for what this agent
        can do for that object / location.

        Example usecase: tasking another agent that is not yourself, e.g. to
        move an object.

        For the default MATRX visualization, the context menu is opened by
        right clicking on an object. This function should generate a list of
        options (actions, messages, or something else) which relate to that
        object or location. Each option is in the shape of a text shown in the
        context menu, and a message which is send to this agent if the user
        actually clicks that context menu option.

        Parameters
        ----------
        agent_id_who_clicked : str
            The ID of the (human) agent that selected this agent and requested
            for a context menu.
        clicked_object_id : str
            A string indicating the ID of an object. Is None if the user
            clicked on a background tile (which has no ID).
        click_location : list
            A list containing the [x,y] coordinates of the object on which the
            user right clicked.

        Returns
        -------
         context_menu : list
            A list containing context menu items. Each context menu item is a
            dict with a 'OptionText' key, which is the text shown in the menu
            for the option, and a 'Message' key, which is the message instance
            that is sent to this agent when the user clicks on the context
            menu option.
        """
        print("Context menu other")
        context_menu = []

        # Generate a context menu option for every action
        for action in self.action_set:
            context_menu.append({
                "OptionText": f"Do action: {action}",
                "Message": Message(content=action, from_id=clicked_object_id,
                                   to_id=self.agent_id)
            })
        return context_menu

    def __select_random_obj_in_range(self, state, range_,
                                     property_to_check=None):

        # Get all perceived objects
        object_ids = list(state.keys())

        # Remove world from state
        object_ids.remove("World")

        # Remove self
        object_ids.remove(self.agent_id)

        # Remove all (human)agents
        object_ids = [obj_id for obj_id in object_ids if "AgentBrain" not in
                      state[obj_id]['class_inheritance'] and
                      "AgentBody" not in state[obj_id]['class_inheritance']]

        # find objects in range
        object_in_range = []
        for object_id in object_ids:

            # Select range as just enough to grab that object
            dist = int(np.ceil(np.linalg.norm(
                np.array(state[object_id]['location'])
                - np.array(state[self.agent_id]['location']))))
            if dist <= range_:
                # check for any properties specifically specified by the user
                if property_to_check is not None:
                    if property_to_check in state[object_id] \
                            and state[object_id][property_to_check]:
                        object_in_range.append(object_id)
                else:
                    object_in_range.append(object_id)

        # Select an object if there are any in range
        if object_in_range:
            object_id = self.rnd_gen.choice(object_in_range)
        else:
            object_id = None

        return object_id


class CollectableBlock(EnvObject):
    '''
    Objects that can be collected by agents.
    '''

    def __init__(self, location, name, visualize_shape, img_name):
        super().__init__(location, name, is_traversable=True, is_movable=True,
                         visualize_shape=visualize_shape, img_name=img_name,
                         visualize_size=object_size, class_callable=CollectableBlock,
                         is_drop_zone=False, is_goal_block=False, is_collectable=True)


class ObstacleObject(EnvObject):
    '''
    Obstacles that can be removed by agents
    '''

    def __init__(self, location, name, visualize_shape, img_name):
        super().__init__(location, name, is_traversable=False, is_movable=True,
                         visualize_shape=visualize_shape, img_name=img_name,
                         visualize_size=1.25, class_callable=ObstacleObject,
                         is_drop_zone=False, is_goal_block=False, is_collectable=False)
