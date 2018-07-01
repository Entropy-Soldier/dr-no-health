# Copyright 2018 Entropy-Soldier
#
# Licensed under the MIT license: http://opensource.org/licenses/MIT
# This file may not be copied, modified, or distributed except according to those terms.
#
# GE:S and its python library are licensed under the GNU General Public License
# and their usage may be subject to different terms.

from . import GEScenario
from .Utils.GEPlayerTracker import GEPlayerTracker
from .Utils import GetPlayers
import GEEntity, GEPlayer, GEUtil, GEMPGameRules as GERules, GEGlobal as Glb, GEWeapon

USING_API = Glb.API_VERSION_1_2_0
ARMORKILLS = "KillForArmor"

class DrNoHealth(GEScenario):
    '''Armor is the new health!'''

    #-------------------------#
    # Standard GE:S Callbacks #
    #-------------------------#
    
    def __init__(self):
        super(DrNoHealth, self).__init__()
        self.pltracker = GEPlayerTracker( self )

        self.KillsPerArmor = 1 # How many kills it takes before we can pick up a new armorvest.

    def GetPrintName(self):
        return "Dr No Health"

    def GetScenarioHelp( self, help_obj ):
        help_obj.SetDescription( "You have no health, so your armor is the only thing keeping you alive!\n\nYou will die the second your armor bar is depleted, so be sure to stock up on armor as often as you can!\n\n\n\nV3" )

    def GetGameDescription(self):
        if GERules.IsTeamplay():
            return "Team Dr No Health"

        return "Dr No Health"

    def OnLoadGamePlay(self):
        self.CreateCVar( "drnh_killsperarmor", "1", "How many kills to require before a player can pick up armor again" )
        GEUtil.PrecacheSound( "Buttons.beep_ok" )
        self.pltracker.SetValueAll( ARMORKILLS, 0 )

    def OnUnloadGamePlay( self ):
        super( DrNoHealth, self ).OnUnloadGamePlay()
        self.pltracker = None

    def OnCVarChanged( self, name, oldvalue, newvalue ):
        if name == "drnh_killsperarmor":
            newvalueint = max( int( newvalue ), 0 )
            self.KillsPerArmor = newvalueint

            # If we don't have a valid old value for this convar then it means we were using our default value instead.
            oldvalueint = 1

            if oldvalue is not None:
                oldvalueint = int( oldvalue )

            for player in GetPlayers():
                # We've gone from not having enough kills to having too many kills.
                if self.pltracker.GetValue( player, ARMORKILLS ) < oldvalueint and self.pltracker.GetValue( player, ARMORKILLS ) > newvalueint:
                    self.pltracker.SetValue( player, ARMORKILLS, newvalueint ) # Make sure we have just enough to earn our new armor pickup.

                # If we've already earned an armor pickup there's no reason to take it away...but make sure everyone who has yet to earn one
                # gets an update on their progress.
                if self.pltracker.GetValue( player, ARMORKILLS ) < oldvalueint:
                    self.__CheckEnableArmorPickup( player, self.pltracker.GetValue( player, ARMORKILLS ) )

    def OnPlayerConnect( self, player ):
        self.pltracker[player][ARMORKILLS] = 0

    def OnPlayerSpawn(self, player):
        player.SetArmor( int(Glb.GE_MAX_ARMOR) )
        player.SetHealth( 1 ) # We can't actually have 0 health but we can get close!
        player.SetMaxArmor( 0 )
        self.pltracker.SetValue( player, ARMORKILLS, 0 )

        # We may actually want to immediately renable armor pickups if that setting is disabled
        # or we might just need to display the "kills until next pickup" message
        self.__CheckEnableArmorPickup( player, 0 )

    def CalculateCustomDamage( self, victim, info, health, armor ):
        killer = GEPlayer.ToMPPlayer(info.GetAttacker())
        killerid = GEEntity.GetUniqueId(GEPlayer.ToMPPlayer(info.GetAttacker()))
        target = GEEntity.GetUniqueId(victim)
        damage = health + armor
        health = 0

        # Full world damage
        if killer is None:
            armor = damage
        elif killerid == target: # Half self-damage so I can ~rocket jump~
            armor = damage / 2

        # Have to do this here instead of "CanPlayerHaveItem" since if we do it there we don't actually pick the armor up.
        # This method's main purpose is to color the armor bar red, as an indicator to the player they can't pick up any more armor.
        if self.pltracker.GetValue( victim, ARMORKILLS ) < self.KillsPerArmor :
            victim.SetMaxArmor( 0 )

        # We ran out of armor!  Time to die.
        if victim.GetArmor() <= armor:
            health = 160

        return health, armor

    def OnPlayerKilled(self, victim, killer, weapon):
        if not victim: # If there's no victim there's no kill.
            return

        # Scoring is the same as deathmatch.
        killerScoreChange, unused_victimScoreChange = self.__StandardScoringRules( victim, killer )

        # We only change armor progress for the killer.
        if not killer:
            return

        # We only care about the killer score change, as if there is no killer or they're the victim as well,
        # then they just died and their armor kills no longer matter anyway.  If their score change is positive
        # it's a normal kill, if it's negative then they killed a teammate and should lose armor kill progress.
        newArmorKills = self.pltracker.GetValue( killer, ARMORKILLS ) + killerScoreChange
        self.pltracker.SetValue( killer, ARMORKILLS, max( newArmorKills, 0 ) )

        # See if we should enable armor pickups for this player or display a message.
        self.__CheckEnableArmorPickup( killer, newArmorKills )

    def CanPlayerHaveItem( self, player, item ):
        if item.GetClassname().startswith( "item_armorvest" ):
            if player.GetMaxArmor() == 0: # If we can't pick up this armor due to not having enough kills, inform the player as to why.
                killsToNextLevel = self.KillsPerArmor - self.pltracker.GetValue( player, ARMORKILLS )
                if killsToNextLevel == 1:
                    GEUtil.HudMessage( player, "You need 1 more kill to pick up armor!", -1, 0.71, GEUtil.Color( 150, 50, 50, 255 ), 1.0, 1 )
                else:
                    GEUtil.HudMessage( player, "You need " + str(killsToNextLevel) + " more kills to pick up armor!", -1, 0.71, GEUtil.Color( 150, 50, 50, 255 ), 1.0, 1 )
            elif player.GetArmor() < int(Glb.GE_MAX_ARMOR): # If we made it here we're most certainly picking up that armor.
                self.pltracker.SetValue( player, ARMORKILLS, 0 )
                self.__CheckEnableArmorPickup( player, 0 )

        return True

    #-----------------------------------#
    #    Gamemode Specific Functions    #
    #-----------------------------------#

    def __CheckEnableArmorPickup( self, player, armorkills ):
        ''' Check to see if we should enable armor pickups for the given player. '''
        if self.KillsPerArmor <= 0: # This setting is disabled, so always let players pick up armor.
            player.SetMaxArmor( 160 )
            return

        if armorkills == self.KillsPerArmor:
            player.SetMaxArmor( 160 ) # Turn the armor bar blue again.
            GEUtil.PlaySoundToPlayer( player, "Buttons.beep_ok" )
            GEUtil.HudMessage( player, "You've earned an armor pickup!", -1, 0.71, GEUtil.Color( 50, 100, 200, 255 ), 3.0, 1 )
        elif armorkills < self.KillsPerArmor:
            killsToNextLevel = self.KillsPerArmor - armorkills
            if killsToNextLevel == 1:
                GEUtil.HudMessage( player, "1 kill until next armor pickup", -1, 0.71, GEUtil.Color( 50, 100, 200, 255 ), 3.0, 1 )
            else:
                GEUtil.HudMessage( player, str(killsToNextLevel) + " kills until next armor pickup", -1, 0.71, GEUtil.Color( 50, 100, 200, 255 ), 3.0, 1 )

    def __StandardScoringRules( self, victim, killer ):
        '''Apply standard scoring rules and return the changes in points for killer, victim'''
        if not victim:
            return

        if not killer or victim == killer:
            # World kill or suicide
            # GEMPGameRules.GetTeam( victim.GetTeamNumber() ).AddRoundScore( -1 )
            victim.AddRoundScore( -1 )
            return 0, -1
        elif GERules.IsTeamplay() and killer.GetTeamNumber() == victim.GetTeamNumber():
            # Same-team kill
            GERules.GetTeam( killer.GetTeamNumber() ).AddRoundScore( -1 )
            killer.AddRoundScore( -1 )
            return -1, 0

        # Normal kill
        GERules.GetTeam( killer.GetTeamNumber() ).AddRoundScore( 1 )
        killer.AddRoundScore( 1 )
        return 1, 0
