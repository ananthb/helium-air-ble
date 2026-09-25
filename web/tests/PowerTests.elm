module PowerTests exposing (suite)

{-| DPID 0x01 is the unit's on/off state (1 = on); the power draw says whether it
is working. `Power` reads the first and infers nothing from the second.

The figures are real, read off the unit: 19-24 W idle or on the fan alone,
61-91 W while the fan runs on after a power-off, 316-396 W with the inverter
compressor at low output, 645-861 W working hard.

The mirror of `../../tests/test_power.py`.

-}

import Codec
import Dict
import Expect
import Power exposing (Power)
import Test exposing (Test, describe, test)



-- HELPERS


{-| A report of 0x01 and a draw together, as a full status dump carries them.
-}
report : Int -> Int -> Int -> Power -> Power
report flag watts now power =
    reportWith (Dict.fromList [ ( 0x01, flag ), ( 0x1C, watts ) ]) now power


{-| A draw on its own, with no 0x01 in the batch.
-}
draw : Int -> Int -> Power -> Power
draw watts now power =
    reportWith (Dict.fromList [ ( 0x1C, watts ) ]) now power


reportWith : Dict.Dict Int Int -> Int -> Power -> Power
reportWith dps now power =
    Power.report dps (Codec.toStatus dps Codec.initialStatus) now power


on : Int
on =
    1


off : Int
off =
    0



-- TESTS


suite : Test
suite =
    describe "Power"
        [ test "starts off" <|
            \_ -> Expect.equal ( Power.initial.on, Power.initial.running ) ( False, False )
        , test "0x01 is the switch, not the compressor" <|
            -- the measurement this module is built on: fan-only at 24 W, where
            -- the compressor cannot be running, and 0x01 still reads 1
            \_ ->
                Power.initial
                    |> report on 24 0
                    |> (\p -> Expect.equal ( p.on, p.running ) ( True, False ))
        , test "idle at the setpoint is on but not cooling" <|
            \_ ->
                Power.initial
                    |> report on 19 0
                    |> (\p -> Expect.equal ( p.on, p.running ) ( True, False ))
        , test "off is reported as zero" <|
            \_ ->
                Power.initial
                    |> report on 800 0
                    |> report off 19 30
                    |> .on
                    |> Expect.equal False
        , test "the power draw alone never decides on or off" <|
            \_ ->
                Power.initial
                    |> draw 861 0
                    |> (\p -> Expect.equal ( p.on, p.running ) ( False, True ))
        , test "someone used the unit's own remote" <|
            \_ ->
                Power.initial
                    |> report on 700 0
                    |> (\p -> Expect.equal ( p.on, p.running ) ( True, True ))
        , test "off survives a status read that predates it" <|
            -- the status query goes out behind the command, so its answer can
            -- still describe a unit that has not acted yet
            \_ ->
                Power.initial
                    |> report on 861 0
                    |> Power.command False 10
                    |> report on 861 11
                    |> .on
                    |> Expect.equal False
        , test "spin-down does not turn it back on" <|
            \_ ->
                let
                    reports =
                        [ ( 861, 1 ), ( 827, 2 ), ( 645, 3 ), ( 208, 4 ), ( 82, 5 ), ( 81, 6 ) ]

                    after =
                        List.foldl
                            (\( w, t ) ( p, seen ) -> report off w t p |> (\n -> ( n, seen ++ [ n.on ] )))
                            ( Power.initial |> Power.command False 0, [] )
                            reports
                in
                Tuple.second after
                    |> Expect.equal (List.repeat (List.length reports) False)
        , test "an ignored off command gives up" <|
            \_ ->
                let
                    held =
                        Power.initial |> Power.command False 0 |> report on 800 (Power.settle - 1)
                in
                Expect.equal ( held.on, (held |> report on 800 (Power.settle + 1)).on ) ( False, True )
        , test "the hold releases as soon as the unit agrees" <|
            \_ ->
                Power.initial
                    |> Power.command False 0
                    |> report off 19 1
                    |> report on 19 2
                    |> .on
                    |> Expect.equal True
        , test "a batch without 0x01 leaves the state alone" <|
            \_ ->
                Power.initial
                    |> report on 24 0
                    |> draw 340 1
                    |> (\p -> Expect.equal ( p.on, p.running ) ( True, True ))
        , test "low inverter output counts as working" <|
            \_ -> (Power.initial |> report on 340 0).running |> Expect.equal True
        , test "fan run-on does not" <|
            \_ -> (Power.initial |> report on 81 0).running |> Expect.equal False
        , test "a fresh command restarts the window" <|
            \_ ->
                Power.initial
                    |> Power.command False 0
                    |> Power.command True (Power.settle - 1)
                    |> report off 19 (Power.settle + 5)
                    |> .on
                    |> Expect.equal True
        ]
