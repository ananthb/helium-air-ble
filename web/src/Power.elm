module Power exposing (Power, command, initial, report, settle)

{-| Whether the A/C is on, and whether it is working.

The unit reports no power state. DPID 0x01 and the power draw say only whether
it is _working_, so a unit that is on but idle at its setpoint looks exactly like
one that is off. Running is therefore taken as proof that it is on, and off is
only ever known because we asked for it.

That leaves the trap this module exists to close. The status query goes out a
fraction of a second behind a command, and the compressor is still spinning down
when the answer comes back — reading that as "running" turns the unit straight
back on on screen. So a power command is believed until the unit's own report
agrees with it, or until the settle window runs out and the command has
evidently not taken.

The mirror of `custom_components/hlmblue/power.py`, and tested the same way.

@docs Power, command, initial, report, settle

-}

import Codec
import Dict exposing (Dict)


{-| `workingFlag` is the last value seen for DPID 0x01. Most notifications carry
a single datapoint, so it usually is not in the batch in hand, and `holdUntil`
is the tick a command is believed until — 0 when nothing is being held.
-}
type alias Power =
    { on : Bool
    , running : Bool
    , workingFlag : Maybe Int
    , holdUntil : Int
    }


{-| Seconds a power command is believed for. The unit switches off at once but
its fan runs on for about half a minute, and a report taken during that
spin-down still looks like a unit that is running.
-}
settle : Int
settle =
    60


initial : Power
initial =
    { on = False, running = False, workingFlag = Nothing, holdUntil = 0 }


{-| Note that we have asked the unit to turn on or off. `now` is a count of
seconds; only differences matter.
-}
command : Bool -> Int -> Power -> Power
command on now power =
    { power | on = on, holdUntil = now + settle }


{-| Fold in one status report, with `status` already carrying the running total
of the power draw.
-}
report : Dict Int Int -> Codec.Status -> Int -> Power -> Power
report dps status now power =
    let
        workingFlag =
            case Dict.get Codec.dpPower dps of
                Just flag ->
                    Just flag

                Nothing ->
                    power.workingFlag

        running =
            workingFlag == Just 1 || status.watts > Codec.runningWatts

        settled =
            { power | running = running, workingFlag = workingFlag }
    in
    if now < power.holdUntil then
        if running == power.on then
            { settled | holdUntil = 0 }
            -- the unit agrees; watch it again

        else
            settled

    else if running then
        { settled | on = True }

    else
        settled
