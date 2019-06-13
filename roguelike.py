# import libcodpy as tcod # looks deprecated
import tcod

# static variables
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

font_path = 'arial10x10.png'  # unnecessary? this will look in the same folder as this script
# font_path = 'tcod.data.fonts.arial10x10.png' # should really have libtcod full path here ('libtcod/libtcod/data/fonts/arial10x10.png')
font_flags = tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD  # the layout may need to change with a different font file
tcod.console_set_custom_font(font_path, font_flags)

window_title = 'Python 3 libtcod tutorial'
fullscreen = False
tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, window_title, fullscreen)

# Want turnbased? Comment this line
tcod.sys_set_fps(LIMIT_FPS)

# player init variables
player_x = SCREEN_WIDTH // 2
player_y = SCREEN_HEIGHT // 2

# game functions

def handle_keys():
    
    # check for utility keys - fullscreen, exit
    key = tcod.console_check_for_keypress()

    if key.vk == tcod.KEY_ENTER and key.lalt:
        #Alt+Enter: toggle fullscreen
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())
 
    elif key.vk == tcod.KEY_ESCAPE:
        return True  #exit game
 
    # movement keys
    global player_x, player_y
    
    if tcod.console_is_key_pressed(tcod.KEY_UP):
        player_y = player_y - 1
 
    elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
        player_y = player_y + 1
 
    elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
        player_x = player_x - 1
 
    elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
        player_x = player_x + 1




# main loop
while not tcod.console_is_window_closed():

    # '0' is which console we're printing to - here, that's the screen
    # note: drawing before handling key input
    tcod.console_set_default_foreground(0, tcod.white)

    # print character
    tcod.console_put_char(0, 1, 1, '@', tcod.BKGND_NONE)

    # flush changes to screen
    tcod.console_flush()

    # clean space where player just was by printing a space there
    tcod.console_put_char(0, player_x, player_y, ' ', tcod.BKGND_NONE)
     #handle keys and exit game if needed
    exit = handle_keys()
    if exit:
        break