#!/usr/bin/env python
import tcod
import math
import textwrap

# ######################################################################
# Global Game Settings
# ######################################################################

# Windows Controls
FULLSCREEN = False

SCREEN_WIDTH = 80  # characters wide
SCREEN_HEIGHT = 50  # characters tall
LIMIT_FPS = 20  # 20 frames-per-second maximum
# Game Controls
TURN_BASED = True  # turn-based game
 


#########
## MAP ##
######### 

MAP_WIDTH = 80
MAP_HEIGHT = 43

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30


FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True # light walls or not
TORCH_RADIUS = 10

######
# GUI #
#######

# colors for illuminated and dark walls and floors
color_dark_wall = tcod.Color(0, 0, 100)
color_light_wall = tcod.Color(130, 110, 50)
color_dark_ground = tcod.Color(50, 50, 150)
color_light_ground = tcod.Color(200, 180, 50)

# sizes and coordinates relevant for the GUI
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

INVENTORY_WIDTH = 50
#################################
## Player / Creature Constants ##
#################################

MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2
HEAL_AMOUNT = 4

##################################
## Foundational Classes        ###
##################################

class Tile:
    # a tile on the map, and its properties
    def __init__(self, blocked, block_sight=None):
        self.blocked = blocked
        self.explored = False

        # by default, if a tile is blocked it also blocks sight
        if block_sight is None:
            block_sight = blocked
            self.block_sight = block_sight

class Rect:
    # a rectangle on the map, used to characterize a room
    def __init__(self, x, y, w, h):
        # top left of room - (x1,y1), top right of room (x2,y2)
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        # get a tuple of the room's center
        center_x = (self.x1 + self.x2) // 2
        center_y = (self.y1 + self.y2) // 2
        return (center_x, center_y)

    def intersect(self, other):
        # return true if these two rectangles overlap

        return (self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)


class Object:
    # catch-all object class. Player, monsters, item, everything will be a character on-screen.

    def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None, item=None):
        self.x = x
        self.y = y
        
        self.char = char
        self.name = name

        self.color = color      
        self.blocks = blocks

        # Component allowances
        # So, this is the only place self.____.owner is set. The component is told who owns it by passing 'self' over, so that value IS held on the component. But note, there's no default value on the component. Not the most readable; the 'owner' code only lives here.

        # Fighter
        self.fighter = fighter
        
        if self.fighter: 
            # let fighter component know who owns it
            self.fighter.owner = self

        # AI
        self.ai = ai
        if self.ai:
            # let AI component know who owns it
            self.ai.owner = self

        # Item
        self.item = item
        if self.item: # let item component know who owns it
            self.item.owner = self

    def move(self,dx,dy):
        # move by a delta, unless destination is blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def draw(self):
        # set color, draw char at this position (but only if player can see it in FOV)
        if tcod.map_is_in_fov(fov_grid, self.x, self.y):
            tcod.console_set_default_foreground(con, self.color)
            tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

    def clear(self):
        # erase this character that represents this obj
        tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)

    def move_towards(self, target_x, target_y):
        # vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y

        distance = math.sqrt(dx ** 2 + dy ** 2)

        # normalize to length 1, preserve direction. Round it, convert to integer so answer is in grid units

        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx,dy)

    def distance_to(self, other):
        # return distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx **2 + dy ** 2)

    def send_to_back(self):
        # make this object be drawn first, so that others appear above it if on same tile
        global objects
        objects.remove(self)
        objects.insert(0, self)

#####################
### Components   #####
######################


class Item:
    # an item that can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function

    def use(self):
        # just call the "use_function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) # destroy after use, unless cancelled for some reason



    def pick_up(self):
        # add to player inventory, remove from  map.
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', tcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message("Picked up a " + self.owner.name + "!", tcod.green)

# NOTE: Does this go here? (should this be aligned all the way left? or nested?)
def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', tcod.red)
        return 'cancelled'
 
    message('Your wounds start to feel better!', tcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

class Fighter:
    # combat related properties and methods (monster, player, NPC)
    def __init__(self, hp, defense, power, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function

    def take_damage(self, damage):
        # apply damage if possible
        if damage > 0:
            self.hp -= damage

            # check for death. If there's a death function, call it!
            if self.hp <= 0:
                df = self.death_function
                if df is not None:
                    df(self.owner)

    def attack(self, target):
        # a simple formula for attack damage
        damage = self.power - target.fighter.defense

        # lazy random damage
        # damage = int(self.power * (tcod.random_get_int(0,75,125) / 100)) - target.fighter.defense

        if damage > 0:
            if target.name == 'player':
                text_color = tcod.red
            else:
                text_color = tcod.green
            # make target take some damage
            message(str(self.owner.name.capitalize()) + ' attacks ' + str(target.name) + ' for ' + str(damage) + ' HP!', text_color)
            target.fighter.take_damage(damage)
        else:
            message(str(self.owner.name.capitalize()) + 'attacks ' + str(target.name) + ' but it has no effect!', tcod.white)

    def heal(self, amount):
        #heal by the given amount, without going over the maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    # AI for a basic monster
    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it can see you.
        monster = self.owner

        if tcod.map_is_in_fov(fov_grid, monster.x, monster.y):

            # move towards player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)

            # close enough - attack time, if player alive!
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class BossMonster:
    # AI for a heavy hitting boss monster
    def __init__(self):
        self.charged = 0

    def take_turn(self):
        # a basic monster takes its turn. If you can see it, it can see you.
        monster = self.owner
        if tcod.map_is_in_fov(fov_grid, monster.x, monster.y):

            # random actions: roll for action
            action_roll = tcod.random_get_int(0,0,100)

            if action_roll <= 20:
                message(str(self.owner.name) + ' roars a challenge!', tcod.white)

            else:
                if action_roll > 70 and self.charged == 0:
                    message(str(self.owner.name) + ' draws itself up to its full height!', tcod.white)
                    self.charged = 1
                    print("DEBUG LOG: DRAGON CHARGED = " + str(self.charged), tcod.white)

                # if it's time, breathe some fire
                elif monster.distance_to(player) <= 3 and action_roll > 85 and self.charged == 1:
                        self.boss_action(player)
                        self.charged = 0
                # move towards player if far away
                elif monster.distance_to(player) >= 2:
                    monster.move_towards(player.x, player.y)

                # close enough - attack time, if player alive!
                elif player.fighter.hp > 0:
                        monster.fighter.attack(player) 

    def boss_action(self, target):
        # boss actions should really live under the fighter class, right? They're boss moves? but the AI logic fits better in the monster AI class...

        # oh, instead of monster attack, they should have their own boss attack method, which has all this logic. that'd keep the AI here and the rest in the attacks.

        # Either way, dragons now rock you. Sweet.
        if self.owner.name == 'Dragon':
            message(str(self.owner.name) + ' breathes fire!', tcod.white)
            # dragons breathe fire. It's bad for ya.
            damage = self.owner.fighter.power + tcod.random_get_int(0,2,5) - target.fighter.defense

        if damage > 0:
            text_color = tcod.orange

            # make target take some damage
            message('** ' + str(self.owner.name.capitalize()) + ' attacks ' + str(target.name) + ' for ' + str(damage) + ' HP! **', text_color)
            target.fighter.take_damage(damage)

################
## Functions ###
################

## Map construction ##

def create_room(room):
    global grid

    # go through tiles in rectangle and make them passable
    # note that range() will stop one short of the second argument, so that's the far boundary (room includes an outer wall).
    # likewise, start from x1 + 1 to have a near wall too

    for x in range(room.x1 + 1, room.x2):
        for y in range(room.x1 + 1, room.y2):
            grid[x][y].blocked = False
            grid[x][y].block_sight = False

def create_h_tunnel(x1,x2,y):
    global grid
    # horizontal tunnel

    # oh, this is clever - always ensure the for loop gets the smaller of x1 and x2 first, to properly loop

    for x in range(min(x1,x2),max(x1,x2)+1):
        grid[x][y].blocked = False
        grid[x][y].block_sight = False

def create_v_tunnel(y1,y2,x):
    global grid

    # vertical tunnel
    for y in range(min(y1,y2),max(y1,y2)+1):
        grid[x][y].blocked = False
        grid[x][y].block_sight = False

def make_grid():
    global grid, player # can't call this map, it's a named function

    # fill map with "blocked" tiles - rooms will be carved out of rock, more or less

    grid = [[Tile(True)
            for y in range(MAP_HEIGHT)]
            for x in range(MAP_WIDTH)]

    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        # random width and height
        # first argument is which "stream" to get number from, ~= seed?
        w = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = tcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)

        # random room positions, but within map bonds
        x = tcod.random_get_int(0,0, MAP_WIDTH - w - 1)
        y = tcod.random_get_int(0,0, MAP_HEIGHT - h - 1)

        # Rect class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)

        # run through other rooms and see if they intersect with this one
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break
                # wow this is sloppy - if any room overlaps...what, skip? Yep

        if not failed:
            # this means there are on intersections, so this room is valid - time to actually build the room

            # "paint" it to the grid's tiles
            create_room(new_room)

            # center coordinates are handy
            (new_x, new_y) = new_room.center()

            if num_rooms == 0:
                # first room! Place the player here
                player.x = new_x
                player.y = new_y

            else:
                 # for all rooms after the first, time to connect the new room to the last one with two tunnels. Generally, will need an h tunnel and v tunnel; this randomly chooses which to start with. AND, if you really only need one, the other tunnel is one tile, nbd.

                 # center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms-1].center()

                 # flip for it - either start with an h tunnel or v tunnel

                if tcod.random_get_int(0, 0, 1) == 1:
                    # horizontal tunnel first, then vertical
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, prev_x)
                else:
                    # vertical, then horizontal
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, prev_y)

            #add some contents to this room, such as monsters
            place_objects(new_room)

            # Append new room to the list
            rooms.append(new_room)
            num_rooms += 1


def render_all():
    global fov_grid, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute

    if fov_recompute:
        # recompute FOV if player moved, tile changed, etc
        fov_recompute = False
        tcod.map_compute_fov(fov_grid, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        # set all tiles' background color - now, include FOV too
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = tcod.map_is_in_fov(fov_grid, x, y)
                wall = grid[x][y].block_sight

                if not visible:
                    # if it's not visible right now, player can only see it if it's explored
                    if grid[x][y].explored:

                        # tile is OUT of player's FOV
                        if wall:
                            tcod.console_set_char_background(con, x, y,color_dark_wall, tcod.BKGND_SET)
                        else:
                            tcod.console_set_char_background(con, x, y, color_dark_ground, tcod.BKGND_SET)

                else:
                    # tile is IN of player's FOV
                    if wall:
                        tcod.console_set_char_background(con, x, y,color_light_wall, tcod.BKGND_SET)
                    else:
                        tcod.console_set_char_background(con, x, y, color_light_ground, tcod.BKGND_SET)

                    # I think this makes sense here? See it = Explored it
                    grid[x][y].explored = True

    # # draw all objects in the list
    for object in objects:
        if object != player:
            object.draw()
    player.draw()


    #blit the contents of "con" to the root console and present it
    tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
    

    # prepare to render the GUI panel
    tcod.console_set_default_background(panel, tcod.black)
    tcod.console_clear(panel)

    # render message log
    # print game messages, one line at a time

    y = 1
    for (line, color) in game_msgs:
        tcod.console_set_default_foreground(panel, color)
        tcod.console_print_ex(panel, MSG_X, y, tcod.BKGND_NONE, tcod.LEFT, line)
        y += 1

    # player stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, tcod.light_red, tcod.darker_red)

    
    # display name of objects under the mouse
    tcod.console_set_default_foreground(panel, tcod.light_gray)
    tcod.console_print_ex(panel, 1, 0, tcod.BKGND_NONE, tcod.LEFT, get_names_under_mouse())


    # blit console of panel
    tcod.console_blit(panel, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, PANEL_Y)


    

def place_objects(room):
    # choose a random number of monsters
    num_monsters = tcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        #choose random spot for this monster
        x = tcod.random_get_int(0, room.x1+1, room.x2-1)
        y = tcod.random_get_int(0, room.y1+1, room.y2-1)

        if not is_blocked(x,y):
            monster_roll = tcod.random_get_int(0,0,100)
            if monster_roll <= 70:
                # 70% chance of orc
                fighter_component = Fighter(hp=10, defense=0,power=3, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'o', 'Orc', tcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)

            elif monster_roll >= 97:
                # 7% chance of Dragon, it will rock you
                fighter_component = Fighter(hp=30, defense=2,power=4, death_function=monster_death)
                ai_component = BossMonster()

                monster = Object(x, y, 'D', 'Dragon', tcod.red, blocks=True, fighter=fighter_component, ai=ai_component)
            else:
                # 23% chance - otherwise, it's a troll

                fighter_component = Fighter(hp=16, defense=1,power=4, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x,y, 'T', 'Troll', tcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    num_items = tcod.random_get_int(0,0, MAX_ROOM_ITEMS)

    for i in range(num_items):
        # choose item location
        x = tcod.random_get_int(0, room.x1+1, room.x2-1)
        y = tcod.random_get_int(0, room.y1+1, room.y2-1)

        # only place if space not blocked
        if not is_blocked(x,y):
            # create healing potion
            # use_function will determine what the item does
            item_component = Item(use_function=cast_heal)
            item = Object(x,y, '!', 'healing potion', tcod.violet, item=item_component)

            objects.append(item)
            item.send_to_back() # items are rendered behind other objects
    
def is_blocked(x,y):
    # test the map tile
    if grid[x][y].blocked:
        return True

    # check for blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False

#### Player Actions

def player_move_or_attack(dx, dy):
    global fov_recompute

    # the coordinates the player is moving to, attacking
    x = player.x + dx
    y = player.y + dy

    # OBJECT might be an illegal name
    # test for target at new location
    target = None 
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

# attack if found
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx,dy)
        fov_recompute = True

def player_death(player):
    # the game ended!
    global game_state
    message('You died!', tcod.dark_red)
    game_state = 'dead'

    # create player corpse
    player.char = '%'
    player.color = tcod.dark_red

def monster_death(monster):
    # make a monster corpse - doesn't attack, move, can't be hit
    message(str(monster.name.capitalize()) + ' is dead!', tcod.yellow)
    monster.char = '%'
    monster.color = tcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + str(monster.name)
    monster.send_to_back()


def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    # render a bar (hp, xp, etc) at bottom of screen
    # -> first get width of bar
    bar_width = int(float(value) / maximum * total_width)

    #render the background first
    tcod.console_set_default_background(panel, back_color)
    tcod.console_rect(panel, x, y, total_width, 1, False, tcod.BKGND_SCREEN)

    # now render the bar on top:
    tcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        tcod.console_rect(panel, x, y, bar_width, 1, False, tcod.BKGND_SCREEN)

    # centered text with numerical value in bar
    tcod.console_set_default_foreground(panel, tcod.white)
    stats = str(name) + ': ' + str(value) + '/' + str(maximum)
    tcod.console_print_ex(panel, int(x + total_width / 2), y, tcod.BKGND_NONE, tcod.CENTER, stats)

def message(new_msg, color = tcod.white):
    # split message if necessary to multi-line (wordwrap)
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        # buffer full? Remove first line to make room for next one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        # add the new line as a tuple, with the text and color
        game_msgs.append( (line, color) )

# ######################################################################
# User Input
# ######################################################################
# def get_key_event(turn_based=None):
#     if turn_based:
#         # Turn-based game play; wait for a key stroke
#         key = tcod.console_wait_for_keypress(True)
#     # else:
#         # Real-time game play; don't wait for a player's key stroke
#         # key = tcod.console_check_for_keypress() # removed for now.... DEPRECATED with mouse look?
#     return key
 
 
def handle_keys():
    
    global fov_recompute, key

    # key = get_key_event(TURN_BASED)
 
    if key.vk == tcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle fullscreen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())
 
    elif key.vk == tcod.KEY_ESCAPE:
        return 'exit'  # return exit text
    
    if game_state == 'playing':
        # # movement keys - RTS, keeping just in case
        # if tcod.console_is_key_pressed(tcod.KEY_UP):
        #     player_move_or_attack(0,-1)
            
     
        # elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
        #     player_move_or_attack(0,1)
            
        # elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
        #     player_move_or_attack(-1,0)
            
        # elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
        #     player_move_or_attack(1,0)
        

        # movement keys
        if key.vk == tcod.KEY_UP:
            player_move_or_attack(0,-1)
            
     
        elif key.vk == tcod.KEY_DOWN:
            player_move_or_attack(0,1)
            
        elif key.vk == tcod.KEY_LEFT:
            player_move_or_attack(-1,0)
            
        elif key.vk == tcod.KEY_RIGHT:
            player_move_or_attack(1,0)

        else:
            # test for other keys
            key_char = chr(key.c)

            if key_char == 'g':
                # pick up an item
                for object in objects: # look for an item in player's tile
                    if object.x == player.x and object.y == player.y and object.item:
                        print('Found one!')
                        object.item.pick_up()
                        break

            if key_char == 'i':
                # show inventory
                chosen_item = inventory_menu('Press any key next to an item to use it, or any other to cancel. \n')
                # print(str(chosen_item))
                if chosen_item is not None:
                    # print('Debug: Using item named' + str(chosen_item))
                    chosen_item.use()

            return 'didnt-take-turn'

def get_names_under_mouse():
    global mouse

    # return a string with all the names of objects under the mouse
    (x, y) = (mouse.cx, mouse.cy)

    # create a list of those names, if they're in player's FOV
    names = [obj.name for obj in objects
        if obj.x == x and obj.y == y and tcod.map_is_in_fov(fov_grid, obj.x, obj.y)]

    # join list into string, comma separated
    names = ', '.join(names)
    return names.capitalize()

def menu(header, options, width):
    if len(options) > 26: 
        raise ValueError('Cannot have a menu with more than 26 options.')

    # calculate total height for the header (after auto-wrap) and one line per option:
    header_height = tcod.console_get_height_rect(con,0,0,width, SCREEN_HEIGHT, header)
    height = len(options) + header_height

    # create off-screen console that represents the menu's window
    window = tcod.console_new(width, height)

    # print the header, with auto-wrap
    tcod.console_set_default_foreground(window, tcod.white)
    tcod.console_print_rect_ex(window,0,0,width,height,tcod.BKGND_NONE, tcod.LEFT, header)

    # print all menu options
    y = header_height
    letter_index = ord('a')

    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        tcod.console_print_ex(window, 0, y, tcod.BKGND_NONE, tcod.LEFT, text)
        y += 1
        letter_index += 1

    # blit contents of "window" to root console
    # NOTE: Made each of these int's since the code geeked otherwise. However
    # v low menu screen
    x = int(SCREEN_WIDTH/2 - width/2)
    y = int(SCREEN_HEIGHT/2 - height/2)
    tcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
    # foreground, background transparency are last two params ^. Overlays the 
    # menu!

    # present the menu, wait for keypress
    tcod.console_flush()
    key = tcod.console_wait_for_keypress(True)

    # convert ASCII Code to an index, if it matches an option return it
    index = key.c - ord('a')
    print('Debug: Index =' + str(index))
    if index >= 0 and index < len(options):
        print('Returning index')
        return index
    return None


def inventory_menu(header):
    # show a menu with each item of the inventory as an option
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    # if an item was chosen, return it
    if index is None or len(inventory) == 0: 
        return None
    return inventory[index].item


#############################################
# Initialization and Main Game Loop #########
#############################################
 
# Setup Font
font_filename = 'arial10x10.png'
tcod.console_set_custom_font(font_filename, tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD)

# Initialize screen, then buffer console
title = 'Python 3 + Libtcod tutorial'
tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, title, FULLSCREEN)

# Set FPS
tcod.sys_set_fps(LIMIT_FPS)

# buffer console
con = tcod.console_new(MAP_WIDTH, MAP_HEIGHT)

panel = tcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

# create object representing player
fighter_component = Fighter(hp=30,defense=2,power=5, death_function=player_death)
player = Object(0, 0, '@', 'player', tcod.white, blocks=True, fighter=fighter_component)


# add those objects to a list with those two
objects = [player]


# handle inventory
inventory = []

# draw the grid (the map)
make_grid()


# Initialize FOV Module - sightlines and pathing, via tcod's FOV algo

fov_grid = tcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
        tcod.map_set_properties(fov_grid, x, y, not grid[x][y].block_sight, not grid[x][y].blocked)

fov_recompute = True
game_state = 'playing'
player_action = None

# message console
game_msgs = []
message('Welcome to hell, meatbag! No one has survived before, best of luck kiddo.', tcod.red)

mouse = tcod.Mouse()
key = tcod.Key()

while not tcod.console_is_window_closed():
    
    tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)

    # render the screen
    render_all()

    tcod.console_flush()
    
    #erase all objects at their old locations, before they move
    for object in objects:
        object.clear()

    #player turn: handle keys and exit game if needed
    player_action = handle_keys()

    if player_action == 'exit':
        break

    # monster turns
    if game_state == 'playing' and player_action != 'didnt-take-turn':
        for object in objects:
            if object.ai:
                object.ai.take_turn()
