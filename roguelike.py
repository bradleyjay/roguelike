#!/usr/bin/env python
import tcod
 
# ######################################################################
# Global Game Settings
# ######################################################################

# Windows Controls
FULLSCREEN = False

SCREEN_WIDTH = 80  # characters wide
SCREEN_HEIGHT = 50  # characters tall
LIMIT_FPS = 20  # 20 frames-per-second maximum
# Game Controls
TURN_BASED = False  # turn-based game
 


#########
## MAP ##
######### 

MAP_WIDTH = 80
MAP_HEIGHT = 45

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

# colors for illuminated and dark walls and floors
color_dark_wall = tcod.Color(0, 0, 100)
color_light_wall = tcod.Color(130, 110, 50)
color_dark_ground = tcod.Color(50, 50, 150)
color_light_ground = tcod.Color(200, 180, 50)

#################################
## Player / Creature Constants ##
#################################

MAX_ROOM_MONSTERS = 3

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

    def __init__(self, x, y, char, name, color, blocks=False):
        self.x = x
        self.y = y
        
        self.char = char
        self.name = name

        self.color = color      
        self.blocks = blocks

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

    # # draw all objects in the list (but now, only if they're in FOV) (might have mucked this up)
    # if tcod.map_is_in_fov(fov_map, self.x, self.y):
    #     for object in objects:
    #         object.draw()
    for object in objects:
        object.draw()


    #blit the contents of "con" to the root console and present it
    tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
    
    # mark this tile "explored"

def place_objects(room):
    # choose a random number of monsters
    num_monsters = tcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        #choose random spot for this monster
        x = tcod.random_get_int(0, room.x1, room.x2)
        y = tcod.random_get_int(0, room.y1, room.y2)

        if not is_blocked(x,y):
            if tcod.random_get_int(0,0,100) < 80:
                # 80% chance of orc
                monster = Object(x, y, 'o', 'Orc', tcod.desaturated_green, blocks=True)
            else:
                # otherwise, it's a troll
                monster = Object(x,y, 'T', 'Troll', tcod.darker_green, blocks=True)
            objects.append(monster)

    
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
        if object.x == x and object.y == y:
            target = object
            break

# attack if found
    if target is not None:
        print('Gotcha')
    else:
        player.move(dx,dy)
        fov_recompute = True

# ######################################################################
# User Input
# ######################################################################
def get_key_event(turn_based=None):
    if turn_based:
        # Turn-based game play; wait for a key stroke
        key = tcod.console_wait_for_keypress(True)
    else:
        # Real-time game play; don't wait for a player's key stroke
        key = tcod.console_check_for_keypress()
    return key
 
 
def handle_keys():
    
    global fov_recompute

    key = get_key_event(TURN_BASED)
 
    if key.vk == tcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle fullscreen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())
 
    elif key.vk == tcod.KEY_ESCAPE:
        return 'exit'  # return exit text
    
    if game_state == 'playing':
        # movement keys
        if tcod.console_is_key_pressed(tcod.KEY_UP):
            player_move_or_attack(0,-1)
            fov_recompute = True
     
        elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
            player_move_or_attack(0,1)
            fov_recompute = True
        elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
            player_move_or_attack(-1,0)
            fov_recompute = True
        elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
            player_move_or_attack(1,0)
            fov_recompute = True
        else:
            return 'didnt-take-turn'
 
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
con = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

# create object representing player
player = Object(0, 0, '@', 'player', tcod.white, blocks=True) # 



# add those objects to a list with those two
objects = [player]

# draw the grid (the map)
make_grid()

game_state = 'playing'
player_action = None

# Initialize FOV Module - sightlines and pathing, via tcod's FOV algo

fov_grid = tcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
        tcod.map_set_properties(fov_grid, x, y, not grid[x][y].block_sight, not grid[x][y].blocked)

fov_recompute = True

while not tcod.console_is_window_closed():
    
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
            if object != player:
                print('The ' + str(object.name) + ' growls!')
