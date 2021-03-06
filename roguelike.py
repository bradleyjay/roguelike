#!/usr/bin/env python
import tcod
import math
import textwrap
import random

# ######################################################################
# Global Game Settings
# ######################################################################

# Windows Controls
FULLSCREEN = False

SCREEN_WIDTH = 80  # characters wide
SCREEN_HEIGHT = 50  # characters tall
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

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
# MAX_ROOMS = 30 # math'd out in place rooms


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

# MAX_ROOM_MONSTERS = 3 # math'd out in Place Objects
# MAX_ROOM_ITEMS = 2  # math'd out in Place Objects

LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

INVENTORY_WIDTH = 50
HEAL_AMOUNT = 4

LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5

FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 8

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

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

    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None):
        self.always_visible = always_visible

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
        if tcod.map_is_in_fov(fov_grid, self.x, self.y) or (self.always_visible and grid[self.x][self.y].explored):
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

    def evade_vector(self, target_x, target_y):
        # vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y

        distance = math.sqrt(dx ** 2 + dy ** 2)

        # normalize to length 1, preserve direction. Round it, convert to integer so answer is in grid units

        dx = -int(round(dx / distance))
        dy = -int(round(dy / distance))

        if is_blocked(self.x + dx, self.y + dy):
            return False
        else:
            return (dx,dy)

    def distance_to(self, other):
        # return distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx **2 + dy ** 2)

    def distance(self, x, y):
        # return distance to any coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

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
        # just call "use_function" if defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        elif self.use_function() != 'cancelled':
            inventory.remove(self.owner) #destroy item after use, unless cancelled
        # else:
        #     message('Item used...ish')

    def pick_up(self):
        # add to player inventory, remove from  map.
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', tcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message("Picked up a " + self.owner.name + "!", tcod.green)

    def drop(self):
        # add to map, remove from inventory
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', tcod.yellow)


class Fighter:
    # combat related properties and methods (monster, player, NPC)
    def __init__(self, hp, defense, power, xp, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.xp = xp
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
                if self.owner != player:
                    player.fighter.xp += self.xp

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
        # heal by given amount, don't go over max
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

class RangedMonster:
    # AI for ranged (reloading / charging) monster
    def __init__(self, attack_range=(2,4), ammo=0):
        self.attack_range = attack_range # always a tuple of preferred range
        self.attack_range_avg = (attack_range[0] + attack_range[1]) // 2
        self.ammo_max = ammo # ammo req'd to shoot. 0 means continuous
        self.ammo = ammo


    def take_turn(self):


        monster = self.owner

        if tcod.map_is_in_fov(fov_grid, monster.x, monster.y):
            # if in FoV

            # player far enough away? not maxed on ammo? reload
            if monster.distance_to(player) >= self.attack_range_avg and self.ammo < self.ammo_max:
                self.stockpile()

            # player out of range, got ammo? advance
            if monster.distance_to(player) > self.attack_range[1] and self.ammo >= self.ammo_max:
                monster.move_towards(player.x, player.y)

            # player far enough away, got ammo? Fire
            elif monster.distance_to(player) >= self.attack_range[0] and monster.distance_to(player) <= self.attack_range[1] and self.ammo == self.ammo_max and player.fighter.hp > 0:
                self.ranged_attack()


            # too close - back up or fire if cornered!
            elif monster.distance_to(player) < self.attack_range[0] and player.fighter.hp > 0:
                evade = monster.evade_vector(player.x, player.y)

                if not evade:
                    if self.ammo < self.ammo_max:
                        self.stockpile()
                    else:
                        self.ranged_attack()
                else:
                    monster.move(evade[0],evade[1])

    def stockpile(self):
        self.ammo += 1
        message('The ' + self.owner.name + ' is loads its weapon!', tcod.red)

    def ranged_attack(self):
        self.owner.fighter.attack(player)
        self.ammo -= 1

class ConfusedMonster:
    # AI for a confused monster

    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0: #still confused...
            #move in a random direction:
            self.owner.move(tcod.random_get_int(0,-1,1), tcod.random_get_int(0,-1,1))
            self.num_turns -= 1
        else: #restore previous AI
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', tcod.red)

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

class ConfusedMonster:
    # AI for temporarily confused monster
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0: # still confused
            # move in random direction, decrement turns left
            self.owner.move(tcod.random_get_int(0, -1, 1), tcod.random_get_int(0,-1,1))
            self.num_turns -= 1
        else: #restore previous AI
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', tcod.red)

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
        for y in range(room.y1 + 1, room.y2):
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
    print("\n Attempting Grid generation.\n")
    grid_success = False

    MAX_ROOMS = min( dungeon_level * 3 + 3 , 30)
    # MAX_ROOMS = 2

    while not grid_success:
        global grid, objects, stairs # can't call this map, it's a named function

        objects = [player]
        # fill map with "blocked" tiles - rooms will be carved out of rock, more or less

        grid = [[Tile(True)
                for y in range(MAP_HEIGHT)]
                for x in range(MAP_WIDTH)]

        rooms = []
        num_rooms = 0

        for r in range(MAX_ROOMS):

            # random width and height
            # first argument is which "stream" to get number from, ~= seed?
            w = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            h = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)

            # random room positions, but within map bonds
            x = random.randint(0, MAP_WIDTH - w - 1)
            y = random.randint(0, MAP_HEIGHT - h - 1)

            # Rect class makes rectangles easier to work with
            new_room = Rect(x, y, w, h)

            # run through other rooms and see if they intersect with this one
            failed = False
            for other_room in rooms:
                if new_room.intersect(other_room):
                    failed = True
                    print("\n\nBlocked.\n\n")
                    break
                    # wow this is sloppy - if any room overlaps...what, skip? Yep

            if not failed:
                # this means there are no intersections, so this room is valid - time to actually build the room

                # "paint" it to the grid's tiles
                create_room(new_room)

                # center coordinates are handy
                (new_x, new_y) = new_room.center()
                print((new_x, new_y))
                print(x, y, w, h)
                print(rooms)
                print('\n\n')

                if num_rooms == 0:
                    # first room! Place the player here
                    player.x = new_x
                    player.y = new_y

                else:
                    # for all rooms after the first, time to connect the new room to the last one with two tunnels. Generally, will need an h tunnel and v tunnel; this randomly chooses which to start with. AND, if you really only need one, the other tunnel is one tile, nbd.

                    # center coordinates of previous room
                    # (prev_x, prev_y) = rooms[num_rooms-1].center()
                    (prev_x, prev_y) = rooms[-1].center()

                    # flip for it - either start with an h tunnel or v tunnel

                    if random.randint(0, 1) == 1:
                        # horizontal tunnel first, then vertical
                        create_h_tunnel(prev_x, new_x, prev_y)
                        # create_v_tunnel(prev_y, new_y, prev_x)
                        create_v_tunnel(prev_y, new_y, new_x)
                    else:
                        # vertical, then horizontal
                        create_v_tunnel(prev_y, new_y, prev_x)
                        # create_h_tunnel(prev_x, new_x, prev_y)
                        create_h_tunnel(prev_x, new_x, new_y)

                #add some contents to this room, such as monsters
                place_objects(new_room)

                # Append new room to the list
                rooms.append(new_room)
                num_rooms += 1

        # create stairs at center of last OPEN room center. Iterate backwards through list. No possible placement? Reroll the dungeon.

        room = len(rooms) - 1

        while True:
            x, y = rooms[room].center()
            if not is_blocked(x,y):

                stairs = Object(x, y, '<', 'stairs', tcod.white, always_visible=True)
                objects.append(stairs)
                stairs.send_to_back() # draw below monsters
                grid_success = True
                print("Complete:" + str((x,y)) + " and " + str(is_blocked(x,y)))
                break

            room -= 1

            if room <= -1:
                grid_success = False
                rooms = []
                break

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


    # show dungeon level
    tcod.console_print_ex(panel, 1, 3, tcod.BKGND_NONE, tcod.LEFT, 'Dungeon Level ' + str(dungeon_level))


    # display name of objects under the mouse
    tcod.console_set_default_foreground(panel, tcod.light_gray)
    tcod.console_print_ex(panel, 1, 0, tcod.BKGND_NONE, tcod.LEFT, get_names_under_mouse())


    # blit console of panel
    tcod.console_blit(panel, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, PANEL_Y)




def place_objects(room):
    # choose a random number of monsters

    MAX_ROOM_MONSTERS = dungeon_level // 3 + 2
    MAX_ROOM_ITEMS = dungeon_level // 4 + 1
    MAX_ODDS = min(dungeon_level * 5 + 40, 100)


    ## Monsters

    num_monsters = tcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    monster_chances = {'orc': 35, 'archer': 10, 'troll': 20, 'dragon': 15, 'maw': 8, 'lich': 7, 'titan': 5}
    item_chances = {'heal': 45, 'confuse': 20, 'fireball': 20, 'lightning': 20}

    for i in range(num_monsters):
        #choose random spot for this monster
        x = tcod.random_get_int(0, room.x1+1, room.x2-1)
        y = tcod.random_get_int(0, room.y1+1, room.y2-1)

        if not is_blocked(x,y):
            # monster_roll = tcod.random_get_int(0,0,100)
            choice = random_choice(monster_chances, MAX_ODDS)

            if choice == 'orc':

                fighter_component = Fighter(hp=10, defense=0,power=3, xp=35, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'o', 'Orc', tcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)

            elif choice == 'archer':

                fighter_component = Fighter(hp=8, defense=0, power=3, xp = 35, death_function=monster_death)
                ai_component = RangedMonster(attack_range=(2,4),ammo=1)

                monster = Object(x,y, 'a', 'Goblin Archer', tcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)

            elif choice == 'troll':
                # 23% chance - otherwise, it's a troll

                fighter_component = Fighter(hp=16, defense=1,power=4, xp = 120, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x,y, 'T', 'Troll', tcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)


            elif choice == 'dragon':
                # 7% chance of Dragon, it will rock you
                fighter_component = Fighter(hp=30, defense=2,power=4, xp=500, death_function=monster_death)
                ai_component = BossMonster()

                monster = Object(x, y, 'D', 'Dragon', tcod.red, blocks=True, fighter=fighter_component, ai=ai_component)

            elif choice == 'maw':
                # needs abilities that debuff and constrict, hits real hard
                # very aggressive AI
                fighter_component = Fighter(hp=50, defense=4,power=8, xp=1000, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'M', 'Maw', tcod.red, blocks=True, fighter=fighter_component, ai=ai_component)

            elif choice == 'lich':
                # will have spells that summon badguys - lich can be fragile-ish
                # should have debuffs, evasive AI
                fighter_component = Fighter(hp=70, defense=4, power=12, xp=1500, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'L', 'Lich', tcod.black, blocks=True, fighter=fighter_component, ai=ai_component)

            elif choice == 'titan':
                # will have spells that summon badguys - lich can be fragile-ish
                # should have debuffs, evasive AI
                fighter_component = Fighter(hp=300, defense=10, power=25, xp=10000, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'T', 'Titan', tcod.white, blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    num_items = tcod.random_get_int(0,0, MAX_ROOM_ITEMS)

    for i in range(num_items):
        # choose item location
        x = tcod.random_get_int(0, room.x1+1, room.x2-1)
        y = tcod.random_get_int(0, room.y1+1, room.y2-1)

        # only place if space not blocked
        if not is_blocked(x,y):

            choice = random_choice(item_chances, MAX_ODDS)

            if choice == 'heal':
                # create healing potion
                item_component = Item(use_function=cast_heal)
                item = Object(x,y, '!', 'healing potion', tcod.violet, item=item_component, always_visible=True)

            elif choice == 'confuse':
                # confuse scroll
                item_component = Item(use_function=cast_confuse)
                item = Object(x,y, '#', 'confuse scroll', tcod.light_yellow, item=item_component, always_visible=True)

            elif choice == 'lightning':
                # lightning scroll
                item_component = Item(use_function=cast_lightning)
                item = Object(x,y, '#', 'lightning scroll', tcod.light_yellow, item=item_component, always_visible=True)


            elif choice == 'fireball':
                # fireball scroll
                item_component = Item(use_function = cast_fireball)
                item = Object(x,y, '#', 'fireball scroll', tcod.light_yellow, item=item_component, always_visible=True)

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


def closest_monster(max_range):
    # find closest enemy, up to a maximum range in player's POV
    closest_enemy = None
    closest_dist = max_range + 1 # start with slightly more than max range

    for object in objects:
        if object.fighter and not object == player and tcod.map_is_in_fov(fov_grid, object.x, object. y):
            # calculate distance between object, player
            dist = player.distance_to(object)
            if dist < closest_dist: # remember closest
                closest_enemy = object
    return closest_enemy

def target_tile(max_range=None):
    # return position of a tile left-clicked by the player in FOV,
    # or(None, None if right-clicked)
    global key, mouse
    while True:
        # render screen, that'll erase the menu and show names of objects under the mouse.
        tcod.console_flush()
        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS|tcod.EVENT_MOUSE,key,mouse)
        render_all()

        (x, y) = (mouse.cx, mouse.cy)

        if mouse.lbutton_pressed and tcod.map_is_in_fov(fov_grid, x, y) and (max_range is None or player.distance(x,y) <= max_range):
            return (x,y)

        if mouse.rbutton_pressed or key.vk == tcod.KEY_ESCAPE:
            return (None, None) # cancel!


def target_monster(max_range=None):
    # returns a clicked monster in FOV up to a range, or None if right clicked

    while True:
        (x, y) = target_tile(max_range)
        if x is None: # player cancelled
            return None

        # return the first-clicked monster, otherwise, keep looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj

def next_level():
    global dungeon_level
    # advance to next level
    message('You take a moment to rest, recovering your strength.', tcod.light_violet)
    player.fighter.heal(player.fighter.max_hp//2)

    message('After a rare moment of peace, you decend deeper into the heart of the dungeon...', tcod.red)

    # new level time
    dungeon_level += 1

    make_grid()

    initialize_fov()



def check_level_up():
    # see if player's xp is enough to level up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        # it is, level
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', tcod.yellow)

        choice = None
        while choice == None:
            # player picks benefit
            choice = menu('Level up! Choose a stat to raise:\n', ['Constitution (+20 HP), from ' + str(player.fighter.max_hp) + ')', 'Strength (+1 attack, from ' + str(player.fighter.power) + ')', 'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

        if choice == 0:
            player.fighter.max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.power += 1
        elif choice == 2:
            player.fighter.defense += 1


def random_choice(chances_dict, MAX_ODDS):
    # choose one option from the list of chances, return its index
    # the dice will land on some number between 1 and the sum of the chances
    # MAX ODDS determine what's available - these increase with dungeon level, and open up new items and monsters to spawn.


    # chances = chances_dict.values()
    # strings = chances_dict.keys()

    # dice = tcod.random_get_int(0, 1, MAX_ODDS)
    dice = random.randint(0, MAX_ODDS)

    # print("DICE: " + str(dice))
    # print("MAX ODDS: " + str(MAX_ODDS))
    # go through all the chances, keeping sum so far
    running_sum = 0
    # choice = 0 # used to return index, but dicts aren't iterable
    # for w in chances:

    for w in chances_dict:

        running_sum += chances_dict[w]
        # how do I iterate through strings, matched with dict? ....don't seperate them, that's dumb. just use the whole dict entry -> return name of choice selected !!

        # see if the dice landed in the part that corresponds with this choice
        if dice <= running_sum:
            return w
        # choice += 1

# def random_choice(chances_dict):
#     # choose one option from dictionary of chances, returning its key
#     # chances = chances_dict.values()
#     # print('CHANCES:' + str(chances))
#     # strings = chances_dict.keys()
#     # print('STRINGS:' + str(strings))

#     # dict.keys and dict.values returns an iterable, NOT indexable object - it's a dict OF the keys? so you can't say "give me dict[1]"
#     # selection = random_choice_index(chances_dict)
#     # print(selection)

#     # print('tests:\n')
#     # print(strings[0])
#     # print(strings[1])
#     # strings[selection]
#     # exit
#     # return strings[random_choice_index(chances)]
#     return random_choice_index(chances_dict)

def msgbox(text, width=50):
    menu(text, [], width) #use menu as a message box



# def from_dungeon_level(table):
#     # returns a number of rooms based on level
#     for (value, level) in reversed(table):
#         if dungeon_level >= level:
#             return value
#     return 0

################################
#### Player Actions   ##########
################################


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
    message(str(monster.name.capitalize()) + ' is dead! You gain ' + str(monster.fighter.xp) + ' XP!', tcod.yellow)
    monster.char = '%'
    monster.color = tcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + str(monster.name)
    monster.send_to_back()


def closest_monster(max_range):
    # find closest enemy, up to a maximum range, and in player's FOV
    closest_enemy = None
    closest_dist = max_range + 1 # start with slightly more than maximum range

    for obj in objects:
        if obj.fighter and not obj == player and tcod.map_is_in_fov(fov_grid, obj.x, obj.y):
            # calculate distance between this object and the player
            dist = player.distance_to(obj)
            if dist < closest_dist: # it's closer, remember it
                closest_enemy = obj
                closest_dist = dist
    return closest_enemy


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

def cast_heal():
    # heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', tcod.red)
        return 'cancelled'

    message('Your wounds start to feel better!', tcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)



def cast_lightning():
    # find closest enemy inside maximum range, damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:
        message('No enemy within range.', tcod.red)
        return 'cancelled'

    # nuke it:
    message('Lightning arcs to strike the ' + monster.name + ' with a deafening crash! The ' + monster.name + ' takes ' + str(LIGHTNING_DAMAGE) + ' damage.', tcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)


def cast_confuse():

    message('Left-click a monster to confuse it, right-click to cancel.')
    monster = target_monster(CONFUSE_RANGE)

    if monster is None:
        message ('No enemy close enough to target Confuse spell.')
        return 'cancelled'

    # swap AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster # don't forget, tell new component who owns it
    message('The eyes of the ' + monster.name + ' glaze over. It starts to stumble around!', tcod.light_green)

def cast_fireball():
    # ask player where to send the fireball
    message('Left click a taget tile for fireball, ESC key or right-click to cancel.', tcod.cyan)
    (x, y) = target_tile()
    if x is None:
        return 'cancelled'

    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', tcod.orange)

    for obj in objects: # damage every fighter in range
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + 'was burned for ' + str(FIREBALL_DAMAGE) + ' HP.', tcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

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

def menu(header, options, width):
    # create general menu!
    if len(options) > 26:
        raise ValueError('Cannot have a menu with more than 26 options, cuz its 1991 right now.')

    # calculate total height for the header (after auto-wrap), and one line per option
    header_height = tcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)

    if header == '':
        header_height = 0

    height = len(options) + header_height

    # create an offscreen where menu's window is drawn first
    window = tcod.console_new(width, height)

    # print header, with auto-wrap
    tcod.console_set_default_foreground(window, tcod.white)
    tcod.console_print_rect_ex(window, 0, 0, width, height, tcod.BKGND_NONE, tcod.LEFT, header)


    # print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ')' + option_text
        tcod.console_print_ex(window, 0, y, tcod.BKGND_NONE, tcod.LEFT, text)
        y+=1
        letter_index += 1

    # blit contents of 'window' to root console
    x = SCREEN_WIDTH//2 - width//2
    y = SCREEN_HEIGHT//2 - height//2
    tcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7) # last two params - foreground and background  transparency

    # present the root console to player, wait for key-pres
    tcod.console_flush()
    key = tcod.console_wait_for_keypress(True)

    if key.vk == tcod.KEY_ENTER and key.lalt:
        tcod.console_set_fullscreen(not tcod.console_is_fullscreen())

    index = key.c - ord('a')
    if index >= 0 and index < len(options):
        return index
    return None

def inventory_menu(header):
    # show a menu with each item of inventory as an option:
    if len(inventory) == 0:
        options = ['Inventory is empty!']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)
    if index is None or len(inventory) == 0:
        return None
    return inventory[index].item

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

            elif key_char == 'i':
                # show inventory
                chosen_item = inventory_menu('Press key next to item to use, or any other to cancel.')
                if chosen_item is not None:
                    chosen_item.use()

            elif key_char == 'd':
                # show inventory, but for dropping:
                chosen_item = inventory_menu('Press key next to any item to DROP that item, or any other to cancel.')
                if chosen_item is not None:
                    chosen_item.drop()

            elif key_char == ',':
                # go down stairs, if player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()

            elif key_char == 'c':
                # show character sheet
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information \n\nLevel: ' + str(player.level) + '\nExperience: ' +  str(player.fighter.xp) + '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) + '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)
            elif key_char == 'm':
                for y in range(MAP_HEIGHT):
                    for x in range(MAP_WIDTH):
                        grid[x][y].explored = True

            # elif key_char == 'a':
            #     chosen_ability = ability_menu('Press key next to any ability to use it, or any other to cancel.')
            #     if chosen_ability is not None:
            #         chosen_ability.use()

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



def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level

    # create object representing player
    fighter_component = Fighter(hp=30,defense=1,power=5, xp=0, death_function=player_death)
    player = Object(0, 0, '@', 'player', tcod.white, blocks=True, fighter=fighter_component)

    player.level = 1

    # draw the grid (the map)
    dungeon_level = 1
    make_grid()

    initialize_fov()
    game_state = 'playing'

    # handle inventory
    inventory = []

    # message console
    game_msgs = []
    message('Welcome to hell, meatbag! No one has survived before, best of luck kiddo.', tcod.red)

def initialize_fov():
    global fov_recompute, fov_grid

    fov_recompute = True

    # Initialize FOV Module - sightlines and pathing, via tcod's FOV algo

    tcod.console_clear(con)  #unexplored areas start black (which is the default background color)

    fov_grid = tcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            tcod.map_set_properties(fov_grid, x, y, not grid[x][y].block_sight, not grid[x][y].blocked)

def play_game():

    global key, mouse
    player_action = None
    mouse = tcod.Mouse()
    key = tcod.Key()

    while not tcod.console_is_window_closed():

        tcod.sys_check_for_event(tcod.EVENT_KEY_PRESS | tcod.EVENT_MOUSE, key, mouse)

        # render the screen
        render_all()

        tcod.console_flush()
        check_level_up()

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


def main_menu():
    img = tcod.image_load('skeletonSplash2.png')



    while not tcod.console_is_window_closed():

        #show image at double console res
        tcod.image_blit_2x(img, 0, 0, 0)

        #show the game's title, and some credits!
        tcod.console_set_default_foreground(0, tcod.red)
        tcod.console_print_ex(0, SCREEN_WIDTH//2, SCREEN_HEIGHT//2-4, tcod.BKGND_NONE, tcod.CENTER,
            'Spooky Spooky Skellies')
        tcod.console_print_ex(0, SCREEN_WIDTH//2, SCREEN_HEIGHT-2, tcod.BKGND_NONE, tcod.CENTER,
            'By Boo Radley Productions')

        #show options and wait on player's choice
        choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)

        if choice == 0:
            new_game()
            play_game()

        elif choice == 2:
            break

main_menu()









