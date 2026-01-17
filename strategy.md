# DuneMUD AI Strategy Guide

## Overview

DuneMUD is a classic LP MUD (Multi-User Dungeon) set in Frank Herbert's Dune universe. It's a text-based multiplayer game where players connect via telnet, explore various planets, kill mobs (NPCs), gain experience, level up, and join guilds with unique abilities.

## Connection Details

- **Address**: dunemud.net
- **Telnet Port**: 6789
- **Secure (TLS) Port**: 6788
- **Protocol**: Telnet with GMCP (Generic Mud Communication Protocol) support

## Game Mechanics

### Character Creation
1. Choose a name (lowercase)
2. Select gender
3. Choose handedness (affects combat)
4. No class/race selection needed at start - very flexible system

### Core Stats
| Stat | Abbreviation | Effect |
|------|--------------|--------|
| Strength (STR) | str | Carry weight, damage, blocking |
| Constitution (CON) | con | Total hitpoints |
| Intelligence (INT) | int | Command Points (CP), mental stamina |
| Wisdom (WIS) | wis | Offense/defense, exp gain, general skills |
| Dexterity (DEX) | dex | Dodge defense |
| Quickness (QUI) | qui | Movement speed, attack frequency |

### Combat System
- Uses a d100 (percentile dice) combat system
- `consider <target>` before attacking to gauge difficulty (count bars)
- `kill <target>` to initiate combat
- Set `wimpy` percentage (recommend 75%) to auto-flee when hurt
- Combat is round-based (2-second rounds)

### Death and Recovery
- Death results in: level loss, stat loss, exp loss, gear loss on corpse
- Respawn in Axotl Tank
- Buy Gholas (clones) at Ghola Regeneration Centers near Astroports (AP)
- Gholas save level/stats but NOT gear/money
- Always `deposit all` money at AP before combat

## Guilds (Factions)

DuneMUD has 10 unique guilds, each with different playstyles:

1. **Atreides** - Noble house, military focused, has medics and support
2. **Fremen** - Desert warriors, crysknife users, water management
3. **Bene Gesserit (BG)** - Mental/physical training, prana-bindu
4. **Bene Gesserit Warriors (BGW)** - Combat-focused Gesserit
5. **Harkonnen** - Brutal tactics, straightforward combat
6. **Sardaukar** - Elite imperial soldiers
7. **Tleilaxu (TLX)** - Genetic manipulation, shape-shifting
8. **Ixians (IMG)** - Technology, implants, nano-bots
9. **Matres** - Combat martial arts, very physical
10. **Speakers** - Support/utility focused

### Guild Selection Strategy for New Players
**Recommended for beginners**: Fremen, Atreides, or Harkonnen (simpler mechanics)
**Complex guilds**: Tleilaxu, Bene Gesserit (require more game knowledge)

## Planets and Travel

### Main Planets
1. **Arrakis** - Desert planet, Fremen territory, spice
2. **Caladan** - Ocean planet, Atreides homeworld
3. **Giedi Prime** - Industrial, Harkonnen territory
4. **Tleilax** - Forests/swamps, Tleilaxu territory
5. **Ix** - Underground tech world, Ixians
6. **Chapterhouse** - Bene Gesserit base
7. **Wallach IX** - Bene Gesserit school world
8. **Salusa Secundus** - Harsh planet, Sardaukar (restricted early access)

### Travel Commands
- Go to AstroPort (AP) on any planet
- `list` - see available shuttles
- `order <shiptype> to <destination>`
- `enter ship` when it arrives

## Key Commands

### Navigation
| Command | Description |
|---------|-------------|
| `n/s/e/w/ne/nw/se/sw/u/d` | Directional movement |
| `look` or `l` | Examine current room |
| `exits` | Show available exits |
| `brief` | Toggle brief room descriptions |

### Information
| Command | Description |
|---------|-------------|
| `score` or `sc` | Character stats/info |
| `inventory` or `i` | Items carried |
| `equipment` or `eq` | Worn items |
| `who` | Online players |
| `help <topic>` | Help system |
| `ghelp <topic>` | Guild-specific help |

### Combat
| Command | Description |
|---------|-------------|
| `consider <target>` | Assess enemy strength |
| `kill <target>` | Attack |
| `wimpy <percent>` | Auto-flee threshold |
| `flee` | Attempt to escape |

### Communication
| Command | Description |
|---------|-------------|
| `say <message>` | Talk in room |
| `tell <player> <message>` | Private message |
| `chat <message>` | Global chat channel |
| `newbie <message>` | Newbie help channel |

### Settings
| Command | Description |
|---------|-------------|
| `set` | View current settings |
| `variables` | List available variables |
| `briefme` | Reduce combat spam |
| `verybriefme` | Further reduce spam |
| `briefmon all` | Reduce monster messages |

## GMCP (Game Management Control Protocol)

DuneMUD supports GMCP for real-time game data. Enable these modules:

### Supported Modules
- **Char** - Character information
- **Room** - Room/location data
- **Comm.Channel** - Channel messages
- **Guild** - Guild-specific data (auto-enabled)

### Key GMCP Messages

#### Char.Name (Login only)
```json
{"name": "playername", "fullname": "Title", "guild": "guildname"}
```

#### Char.Vitals (On change)
```json
{"hp": 123, "maxhp": 200, "sp": 100, "maxsp": 150}
```
- `hp` = Hit Points
- `sp` = Command Points (CP)

#### Char.Stats (On change)
```json
{"str": 10, "con": 12, "int": 8, "wis": 9, "dex": 15, "qui": 17}
```

#### Room.Info (On move)
```json
{
  "name": "Room Name",
  "area": "planetname",
  "num": "room_hash_id",
  "environment": "indoors|outdoors",
  "exits": {"north": "hash", "south": "hash"}
}
```

#### Char.Status (On change)
- `level`, `money`, `bankmoney`, `guild`, `subguild`
- `xp`, `maxxp`, `wimpy`, `wimpy_dir`
- `quest_points`, `kills`, `deaths`, `explorer_rating`

## AI Strategy Execution

### Phase 1: Initial Setup (New Character)
1. Complete login/character creation
2. Run tutorial/newbie academy if available
3. Set essential variables:
   - `wimpy 75`
   - `briefme` or `verybriefme`
   - `briefmon all`
4. Navigate to AstroPort
5. `deposit all` any starting money

### Phase 2: Guild Selection
1. Read about available guilds via `help guilds`
2. Choose based on playstyle preference
3. Navigate to guild headquarters
4. Join the guild
5. Learn basic guild commands via `ghelp`

### Phase 3: Early Game (Levels 1-30)
1. Start in newbie areas:
   - **Arrakis**: Sietch Tabr (coords 18,57)
   - **Caladan**: Forest Brigand Camp (level 10 or lower)
   - **Giedi Prime**: Training Tower (floor 1-3)
   - **Tleilax**: Vent or Basin newbie areas
   - **Ix**: Ixian Caverns
2. Always `consider` before attacking
3. Farm mobs within your level range
4. Return to AP to bank money frequently
5. Advance stats at guild headquarters
6. Get guild weapon/armor if available

### Phase 4: Mid Game (Levels 30-100)
1. Graduate to mid-level areas:
   - **Caladan**: Atreides High School (5-20), No-Ship Crash (60-90)
   - **Giedi Prime**: Training Tower (higher floors), Breeding Facility (25-55)
   - **Arrakis**: Warehouse (25-125), Smuggler's Camp (50-150)
   - **Wallach IX**: Wallach School (35-55), Training Center (65-100)
2. Focus on raising key stats for your guild
3. Complete quests for exp bonuses
4. Explore to increase explorer rating

### Phase 5: Late Game (Levels 100+)
1. Target higher level areas:
   - **Ix**: SCS-RA (50-190), Spire (60-770)
   - **Arrakis**: Sardaukar Facility (275-305)
   - **Chapterhouse**: Desert Base (150-190)
   - **Salusa Secundus**: Cymeks area (275-480)
2. Optimize guild skills
3. Participate in PK if desired (opt-in)

## Combat Decision Making

### When to Attack
- Target is similar or lower level than you
- You have sufficient HP (>75%)
- You have healing available
- You know escape routes

### When to Retreat
- HP drops below wimpy threshold
- Multiple aggressive mobs
- Unable to damage target effectively
- Running low on resources

### Recovery Protocol
1. Flee to safe room
2. Heal (guild-specific method)
3. Rest if needed
4. Bank money
5. Repair/replace gear

## Exploration Strategy

### Mapping Approach
1. Track room IDs via GMCP Room.Info
2. Record exits for each room
3. Note mob levels encountered
4. Mark safe/dangerous areas
5. Identify shortcuts and connections

### Discovery Priority
1. AstroPort locations
2. Guild headquarters
3. Banks/shops
4. Healing locations
5. Training areas by level
6. Quest locations

## Error Recovery

### Common Issues
| Problem | Solution |
|---------|----------|
| Lost | Return to AP, use known paths |
| Low HP | Flee, heal, rest |
| Died | Recover corpse if possible, otherwise restart with ghola |
| Can't hit mob | Train weapon skill, find weaker targets |
| Out of CP | Rest, wait for regeneration |
| Stuck in combat | Use `flee`, set `wimpy` higher |

### Emergency Commands
- `quit` - Save and logout (not in combat)
- `suicide` - Last resort character deletion
- `tell <admin>` - Contact staff for help

## Context Management for AI

### Always Keep in Context
1. This strategy document
2. Current character status (HP, CP, level, location)
3. Current room description and exits
4. Active threats/combat status
5. Current goal/task

### Rotating Context
1. Last 3-5 rooms visited (for backtracking)
2. Recent combat logs
3. Recent chat/communication
4. Recent command outputs

### Discard
1. Old room descriptions (unless mapping)
2. Repetitive combat rounds
3. System messages that have been processed
4. Old character states

## Success Metrics

Track these for progress:
- Character level
- Guild level
- Stats (STR, CON, INT, WIS, DEX, QUI)
- Explorer rating
- Quest points
- Kill count
- Death count (minimize)
- Money accumulated

## Safety Guidelines

1. Never share login credentials
2. Don't spam commands (rate limit)
3. Respect other players
4. Follow game rules (no botting in restricted areas)
5. Don't exploit bugs - report them
6. Be polite on chat channels
