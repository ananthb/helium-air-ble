port module Main exposing (main)

{-| A Web Bluetooth remote for broadcast BLE air conditioners, styled as an LCD remote.

The UI and the whole connection state machine live here, pure. The bytes never
cross this boundary: Elm sends semantic intents out `sendIntent` and receives
decoded status/events on `bleEvents`. Plain JS (js/ble.js, js/codec.js) owns the
Web Bluetooth transport and the wire codec.
-}

import Browser
import Html exposing (..)
import Html.Attributes exposing (..)
import Html.Events exposing (onClick, onInput)
import Json.Decode as D
import Json.Encode as E
import Time



-- PORTS


port sendIntent : E.Value -> Cmd msg


port bleEvents : (D.Value -> msg) -> Sub msg



-- MODEL


type Conn
    = Disconnected
    | Connecting
    | NeedPin
    | Ready


type alias Status =
    { power : Bool
    , temp : Int
    , mode : String
    , fan : String
    , swing : Bool
    , room : Int
    , watts : Int
    }


type alias Model =
    { conn : Conn
    , status : Status
    , pin : String
    , device : Maybe String
    , error : Maybe String
    , backlight : Bool
    , idle : Int
    }


backlightTimeout : Int
backlightTimeout =
    60


modes : List String
modes =
    [ "cool", "dry", "fan", "auto", "heat" ]


fans : List String
fans =
    [ "auto", "low", "medium", "high" ]


init : () -> ( Model, Cmd Msg )
init _ =
    ( { conn = Disconnected
      , status = Status False 24 "cool" "auto" False 0 0
      , pin = "0000"
      , device = Nothing
      , error = Nothing
      , backlight = True
      , idle = 0
      }
    , Cmd.none
    )



-- UPDATE


type Msg
    = Connect
    | Disconnect
    | PinChanged String
    | Login
    | SetPower Bool
    | SetTemp Int
    | CycleMode
    | CycleFan
    | SetSwing Bool
    | Event D.Value
    | Tick


intent : List ( String, E.Value ) -> Cmd Msg
intent fields =
    sendIntent (E.object fields)


next : List String -> String -> String
next xs cur =
    case xs of
        [] ->
            cur

        first :: _ ->
            let
                go list =
                    case list of
                        a :: b :: rest ->
                            if a == cur then
                                b

                            else
                                go (b :: rest)

                        _ ->
                            first
            in
            go xs


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        Tick ->
            let
                i =
                    model.idle + 1
            in
            ( { model | idle = i, backlight = i < backlightTimeout }, Cmd.none )

        Event value ->
            ( applyEvent value model, Cmd.none )

        _ ->
            -- any user interaction wakes the backlight and resets the idle timer
            userUpdate msg { model | idle = 0, backlight = True }


userUpdate : Msg -> Model -> ( Model, Cmd Msg )
userUpdate msg model =
    let
        st =
            model.status
    in
    case msg of
        Connect ->
            ( { model | conn = Connecting, error = Nothing }, intent [ ( "kind", E.string "connect" ) ] )

        Disconnect ->
            ( { model | conn = Disconnected, device = Nothing }, intent [ ( "kind", E.string "disconnect" ) ] )

        PinChanged p ->
            ( { model | pin = String.filter Char.isDigit p |> String.left 4 }, Cmd.none )

        Login ->
            ( model, intent [ ( "kind", E.string "login" ), ( "pin", E.string model.pin ) ] )

        SetPower on ->
            ( model, intent [ ( "kind", E.string "setPower" ), ( "on", E.bool on ) ] )

        SetTemp t ->
            ( model, intent [ ( "kind", E.string "setTemp" ), ( "value", E.int t ) ] )

        CycleMode ->
            ( model, intent [ ( "kind", E.string "setMode" ), ( "value", E.string (next modes st.mode) ) ] )

        CycleFan ->
            ( model, intent [ ( "kind", E.string "setFan" ), ( "value", E.string (next fans st.fan) ) ] )

        SetSwing on ->
            ( model, intent [ ( "kind", E.string "setSwing" ), ( "on", E.bool on ) ] )

        _ ->
            ( model, Cmd.none )


applyEvent : D.Value -> Model -> Model
applyEvent value model =
    case D.decodeValue eventDecoder value of
        Ok (StateEv s dev) ->
            { model
                | conn = s
                , device = orElse dev model.device
                , error = Nothing
            }

        Ok (StatusEv status) ->
            { model | status = status, conn = Ready }

        Ok (ErrorEv m) ->
            { model
                | error = Just m
                , conn =
                    if model.conn == Connecting then
                        Disconnected

                    else
                        model.conn
            }

        Err _ ->
            model


orElse : Maybe a -> Maybe a -> Maybe a
orElse a b =
    case a of
        Just _ ->
            a

        Nothing ->
            b


type Ev
    = StateEv Conn (Maybe String)
    | StatusEv Status
    | ErrorEv String


eventDecoder : D.Decoder Ev
eventDecoder =
    D.field "type" D.string
        |> D.andThen
            (\t ->
                case t of
                    "state" ->
                        D.map2 StateEv
                            (D.field "state" D.string |> D.map connFromString)
                            (D.maybe (D.field "device" D.string))

                    "status" ->
                        D.map StatusEv statusDecoder

                    "error" ->
                        D.map ErrorEv (D.field "message" D.string)

                    _ ->
                        D.fail ("unknown event " ++ t)
            )


connFromString : String -> Conn
connFromString s =
    case s of
        "connecting" ->
            Connecting

        "login" ->
            NeedPin

        "ready" ->
            Ready

        _ ->
            Disconnected


statusDecoder : D.Decoder Status
statusDecoder =
    D.map7 Status
        (D.field "power" D.bool)
        (D.field "temp" D.int)
        (D.field "mode" D.string)
        (D.field "fan" D.string)
        (D.oneOf [ D.field "swing" D.bool, D.succeed False ])
        (D.field "room" D.int)
        (D.field "watts" D.int)



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "stage" ]
        [ div [ class "remote", classList [ ( "asleep", model.conn /= Ready ) ] ]
            [ viewStatusBar model
            , viewLcd model.backlight model
            , viewError model.error
            , viewPad model
            ]
        ]


viewError : Maybe String -> Html Msg
viewError err =
    case err of
        Just e ->
            div [ class "err" ] [ text e ]

        Nothing ->
            text ""



-- STATUS BAR: an indicator LED + Bluetooth logo. Hover shows A/C info.


viewStatusBar : Model -> Html Msg
viewStatusBar model =
    div [ class "statusbar" ]
        [ div [ class "indicator", title (tooltip model) ]
            [ span [ class ("led " ++ ledClass model.conn) ] []
            , img [ class "bt-logo", src btUri, alt "Bluetooth" ] []
            ]
        , span [ class "brand" ] [ text "A/C" ]
        ]


ledClass : Conn -> String
ledClass conn =
    case conn of
        Ready ->
            "btConnected"

        Connecting ->
            "btPairing"

        NeedPin ->
            "btPairing"

        Disconnected ->
            "btDisconnected"


tooltip : Model -> String
tooltip model =
    case model.conn of
        Ready ->
            "Connected to " ++ Maybe.withDefault "the AC" model.device

        Connecting ->
            "Scanning for an A/C…"

        NeedPin ->
            "Connected — enter the passkey to unlock"

        Disconnected ->
            "Disconnected. Tap Connect."


btUri : String
btUri =
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a9c1d6' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M8 8l8 8-4 4V4l4 4-8 8'/%3E%3C/svg%3E"



-- LCD


viewLcd : Bool -> Model -> Html Msg
viewLcd backlight model =
    div [ classList [ ( "lcd", True ), ( "dark", not backlight ) ] ] <|
        case model.conn of
            Ready ->
                viewReadout model.status

            NeedPin ->
                placeholder "LOCKED"

            Connecting ->
                placeholder "SCANNING"

            Disconnected ->
                placeholder "OFFLINE"


viewReadout : Status -> List (Html Msg)
viewReadout st =
    [ div [ class "lcd-top" ]
        [ span [ classList [ ( "seg", True ), ( "on", st.power ) ] ] [ text (String.toUpper st.mode) ]
        , span [ class "room" ] [ text ("IN " ++ String.fromInt st.room ++ "°") ]
        ]
    , div [ class "lcd-main" ]
        [ span [ class "temp" ] [ text (String.fromInt st.temp) ]
        , span [ class "deg" ] [ text "°C" ]
        ]
    , div [ class "lcd-bot" ]
        [ span [ class "field" ] [ label_ "FAN", fanBars st.fan ]
        , span [ classList [ ( "field", True ), ( "on", st.swing ) ] ] [ text "SWING ↕" ]
        , span [ class "field watts" ] [ text (wattsText st) ]
        ]
    ]


placeholder : String -> List (Html Msg)
placeholder caption =
    [ div [ class "lcd-top" ] [ span [ class "seg" ] [ text "----" ], span [ class "room" ] [] ]
    , div [ class "lcd-main" ]
        [ span [ class "temp" ] [ text "--" ]
        , span [ class "deg" ] [ text "°C" ]
        ]
    , div [ class "lcd-bot" ] [ span [ class "field muted" ] [ text caption ] ]
    ]


wattsText : Status -> String
wattsText st =
    if st.watts > 0 then
        String.fromInt st.watts ++ "W"

    else
        "STANDBY"


label_ : String -> Html Msg
label_ s =
    span [ class "lbl" ] [ text s ]


fanBars : String -> Html Msg
fanBars fan =
    let
        lit =
            case fan of
                "low" ->
                    1

                "medium" ->
                    2

                "high" ->
                    3

                _ ->
                    0

        bar i =
            span [ classList [ ( "bar", True ), ( "on", i <= lit ) ] ] []
    in
    if fan == "auto" then
        span [ class "bars auto" ] [ text "AUTO" ]

    else
        span [ class "bars" ] (List.map bar [ 1, 2, 3 ])



-- BUTTON PAD


viewPad : Model -> Html Msg
viewPad model =
    case model.conn of
        Disconnected ->
            div [ class "pad connect" ]
                [ button [ class "btn power big", onClick Connect ] [ text "CONNECT" ] ]

        Connecting ->
            div [ class "pad connect" ]
                [ button [ class "btn big", disabled True ] [ text "SCANNING…" ] ]

        NeedPin ->
            div [ class "pad pinpad" ]
                [ input
                    [ type_ "tel"
                    , value model.pin
                    , onInput PinChanged
                    , class "pin"
                    , attribute "maxlength" "4"
                    , attribute "inputmode" "numeric"
                    ]
                    []
                , button [ class "btn power big", onClick Login ] [ text "UNLOCK" ]
                ]

        Ready ->
            let
                st =
                    model.status
            in
            div [ class "pad grid" ]
                [ button [ classList [ ( "btn", True ), ( "power", True ), ( "on", st.power ) ], onClick (SetPower (not st.power)) ]
                    [ glyph "⏻", small "POWER" ]
                , div [ class "rocker" ]
                    [ button [ class "btn up", onClick (SetTemp (Basics.min 30 (st.temp + 1))) ] [ text "+" ]
                    , span [ class "rocker-lbl" ] [ text "TEMP" ]
                    , button [ class "btn down", onClick (SetTemp (Basics.max 16 (st.temp - 1))) ] [ text "\u{2212}" ]
                    ]
                , button [ class "btn", onClick CycleMode ] [ glyph (modeGlyph st.mode), small "MODE" ]
                , button [ class "btn", onClick CycleFan ] [ glyph "❋", small "FAN" ]
                , button [ classList [ ( "btn", True ), ( "on", st.swing ) ], onClick (SetSwing (not st.swing)) ] [ glyph "↕", small "SWING" ]
                , button [ class "btn ghost", onClick Disconnect ] [ glyph "⏏", small "EXIT" ]
                ]


glyph : String -> Html Msg
glyph g =
    span [ class "glyph" ] [ text g ]


small : String -> Html Msg
small s =
    span [ class "cap" ] [ text s ]


modeGlyph : String -> String
modeGlyph mode =
    case mode of
        "cool" ->
            "❄"

        "heat" ->
            "☀"

        "dry" ->
            "💧"

        "fan" ->
            "❋"

        _ ->
            "⟳"



-- MAIN


main : Program () Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , view = view
        , subscriptions = subscriptions
        }


subscriptions : Model -> Sub Msg
subscriptions _ =
    Sub.batch
        [ bleEvents Event
        , Time.every 1000 (\_ -> Tick)
        ]
