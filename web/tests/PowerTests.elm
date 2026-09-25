module PowerTests exposing (suite)

{-| The unit never says whether it is on, only whether it is working, so `Power`
has to hold a power command until the unit's report catches up.

The watt figures are real, read off the unit through its own power-draw
datapoint: ~19 W in standby, 61-91 W on the fan alone, 316-396 W with the
inverter compressor at low output, and 645-861 W working hard.

The mirror of `../../tests/test_power.py`.

-}

import Codec
import Dict
import Expect
import Power exposing (Power)
import Test exposing (Test, describe, test)



-- HELPERS


{-| A report of `watts`, with no DPID 0x01 in the batch. `Codec.toStatus` folds
the draw in the same way the app does, so the running total is the real one.
-}
draw : Int -> Int -> Power -> Power
draw watts now power =
    reportWith (Dict.fromList [ ( 0x1C, watts ) ]) now power


{-| A report of DPID 0x01 alone, which is how it usually arrives.
-}
workingFlag : Int -> Int -> Power -> Power
workingFlag flag now power =
    reportWith (Dict.fromList [ ( 0x01, flag ) ]) now power


reportWith : Dict.Dict Int Int -> Int -> Power -> Power
reportWith dps now power =
    Power.report dps (Codec.toStatus dps Codec.initialStatus) now power



-- TESTS


suite : Test
suite =
    describe "Power"
        [ test "starts off" <|
            \_ ->
                Expect.equal ( Power.initial.on, Power.initial.running ) ( False, False )
        , test "a running unit is taken as on" <|
            -- someone used the A/C's own remote; the draw is how we find out
            \_ ->
                Power.initial
                    |> draw 827 0
                    |> (\p -> Expect.equal ( p.on, p.running ) ( True, True ))
        , test "off survives the compressor spinning down" <|
            -- the bug: cool -> off appeared to do nothing, because the status
            -- query goes out behind the command and the compressor is still
            -- pulling hundreds of watts when the answer comes back
            \_ ->
                let
                    reports =
                        [ ( 861, 11 ), ( 827, 12 ), ( 645, 13 ), ( 208, 14 ), ( 82, 15 ), ( 81, 16 ) ]
                            ++ [ ( 19, 40 ), ( 19, 70 ), ( 19, 100 ) ]

                    after =
                        List.foldl
                            (\( w, t ) ( p, seen ) -> draw w t p |> (\n -> ( n, seen ++ [ n.on ] )))
                            ( Power.initial |> draw 861 0 |> Power.command False 10, [] )
                            reports
                in
                Tuple.second after
                    |> Expect.equal (List.repeat (List.length reports) False)
        , test "fan run-on is not running" <|
            -- 81 W is the fan alone; under the old 80 W threshold this read as cooling
            \_ ->
                Power.initial
                    |> draw 81 0
                    |> (\p -> Expect.equal ( p.on, p.running ) ( False, False ))
        , test "low inverter output is running" <|
            -- the compressor sustains ~340 W at low output; that is real cooling
            \_ ->
                Power.initial
                    |> draw 340 0
                    |> (\p -> Expect.equal ( p.on, p.running ) ( True, True ))
        , test "an ignored off command gives up" <|
            -- still working once the window closes: the off did not take, and
            -- saying so beats lying indefinitely
            \_ ->
                let
                    held =
                        Power.initial |> Power.command False 0 |> draw 800 (Power.settle - 1)
                in
                Expect.equal ( held.on, (held |> draw 800 (Power.settle + 1)).on ) ( False, True )
        , test "the hold releases as soon as the unit agrees" <|
            \_ ->
                Power.initial
                    |> Power.command False 0
                    |> draw 19 1
                    |> draw 700 2
                    |> .on
                    |> Expect.equal True
        , test "turning on holds through an idle report" <|
            -- on but idle at the setpoint draws no more than the fan, and must
            -- not be read back as off
            \_ ->
                Power.initial
                    |> Power.command True 0
                    |> draw 19 1
                    |> draw 19 (Power.settle + 10)
                    |> .on
                    |> Expect.equal True
        , test "DPID 0x01 alone is enough" <|
            \_ ->
                let
                    on =
                        Power.initial |> workingFlag 1 0
                in
                Expect.equal ( on.running, (on |> workingFlag 0 1).running ) ( True, False )
        , test "a fresh command restarts the window" <|
            \_ ->
                Power.initial
                    |> Power.command False 0
                    |> Power.command True (Power.settle - 1)
                    |> draw 19 (Power.settle + 5)
                    |> .on
                    |> Expect.equal True
        ]
