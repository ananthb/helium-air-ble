module Power exposing (Power, command, initial, report, settle)

{-| Whether the A/C is on, and whether it is working.

DPID 0x01 is the unit's own on/off state, **1 = on, 0 = off**. That is the
inverse of the POWER _command_, where ON is 0 — the same trap as the mode map,
which also differs between what the unit takes and what it reports.

Measured, not inferred: with the unit in fan-only mode and drawing 24 W, well
under `Codec.runningWatts`, it reported 0x01 = 1. The compressor cannot have
been running at that draw, so 0x01 is not a compressor flag. Off at 19 W it
reports 0.

So on/off is read straight from the unit, and the power draw says only whether
it is _working_ — which 0x01 cannot tell you, since a unit idling at its
setpoint is still on.

The one thing a command has to survive is the status read that follows it a
fraction of a second later, which may have been taken before the unit acted. So
a command outranks the unit's report until the report agrees with it, or until
the grace window closes and the command has evidently not taken.

The mirror of `custom_components/hlmblue/power.py`, and tested the same way.

@docs Power, command, initial, report, settle

-}

import Codec
import Dict exposing (Dict)


{-| `holdUntil` is the tick a command is believed until — 0 when nothing is
being held.
-}
type alias Power =
    { on : Bool
    , running : Bool
    , holdUntil : Int
    }


{-| Seconds a power command outranks the unit's own report. Only the status read
taken moments after the command needs covering, and the hold lifts as soon as
the report agrees, so one poll's worth is plenty.
-}
settle : Int
settle =
    30


initial : Power
initial =
    { on = False, running = False, holdUntil = 0 }


{-| Note that we have asked the unit to turn on or off. `now` is a count of
seconds; only differences matter.
-}
command : Bool -> Int -> Power -> Power
command on now power =
    { power | on = on, holdUntil = now + settle }


{-| Fold in one status report, with `status` already carrying the running total
of the power draw.

Most notifications carry a single datapoint, so 0x01 is usually absent from the
batch in hand; the on/off state then simply stands.

-}
report : Dict Int Int -> Codec.Status -> Int -> Power -> Power
report dps status now power =
    let
        settled =
            { power | running = status.watts > Codec.runningWatts }
    in
    case Dict.get Codec.dpPower dps |> Maybe.map ((==) 1) of
        Nothing ->
            settled

        Just reportedOn ->
            if now < power.holdUntil then
                if reportedOn == power.on then
                    { settled | holdUntil = 0 }
                    -- the unit agrees; watch it again

                else
                    settled

            else
                { settled | on = reportedOn }
