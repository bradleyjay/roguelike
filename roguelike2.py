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
TURN_BASED = True  # turn-based game
 
##################
## KEY CLASSES ###
##################

class Object:
    # catch-all object class. Player, monsters, item, everything will be a character on-screen.

    def __init__(self, x, y, char, color):
        self.x = x
        self.y = y
        self.char = char
        self.color = color

    def move(self,dx,dy):
        # move by a delta
        self.x += dx
        self.y += dy

    def draw(self):
        # set color, draw char at this position
        tcod.console_set_default_foreground(con, self.color)
        tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

    def clear(self):
        # erase this character that represents this obj
        tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)




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
 
    key = get_key_event(TURN_BASED)
 
    if key.vk == tcod.KEY_ENTER and key.lalt:
        # Alt+Enter: toggle fullscreen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())
 
    elif key.vk == tcod.KEY_ESCAPE:
        return True  # exit game
 
    # movement keys
    if tcod.console_is_key_pressed(tcod.KEY_UP):
        player.move(0,-1)
 
    elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
        player.move(0,1)
 
    elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
        player.move(-1,0)
 
    elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
        player.move(0,1)
 
 
#############################################
# Main Game Loop
#############################################
 
 

player = Object(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, '@', tcod.white)
npc = Object(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2, '@', tcod.yellow)

objects = [npc, player]

# Setup Font
font_filename = 'arial10x10.png'
tcod.console_set_custom_font(font_filename, tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD)

# Initialize screen, then buffer console
title = 'Python 3 + Libtcod tutorial'
tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, title, FULLSCREEN)

# buffer console
con = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

# Set FPS
tcod.sys_set_fps(LIMIT_FPS)

exit_game = False
while not tcod.console_is_window_closed() and not exit_game:

        #draw all objects in the list
    for object in objects:
        object.draw()

    #blit the contents of "con" to the root console and present it
    tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
    tcod.console_flush()

    #erase all objects at their old locations, before they move
    for object in objects:
        object.clear()

    #handle keys and exit game if needed
    exit = handle_keys()
    if exit:
        break

 
