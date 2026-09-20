port module Main exposing (main)

{-| A/C — a Web Bluetooth control panel for A/Cs.

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
    , room : Int
    , watts : Int
    }


type alias Model =
    { conn : Conn
    , status : Maybe Status
    , pin : String
    , error : Maybe String
    , device : Maybe String
    }


init : () -> ( Model, Cmd Msg )
init _ =
    ( { conn = Disconnected, status = Nothing, pin = "0000", error = Nothing, device = Nothing }
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
    | SetMode String
    | SetFan String
    | Event D.Value


intent : List ( String, E.Value ) -> Cmd Msg
intent fields =
    sendIntent (E.object fields)


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        Connect ->
            ( { model | conn = Connecting, error = Nothing }, intent [ ( "kind", E.string "connect" ) ] )

        Disconnect ->
            ( { model | conn = Disconnected, status = Nothing, device = Nothing }, intent [ ( "kind", E.string "disconnect" ) ] )

        PinChanged p ->
            ( { model | pin = String.filter Char.isDigit p |> String.left 4 }, Cmd.none )

        Login ->
            ( model, intent [ ( "kind", E.string "login" ), ( "pin", E.string model.pin ) ] )

        SetPower on ->
            ( model, intent [ ( "kind", E.string "setPower" ), ( "on", E.bool on ) ] )

        SetTemp t ->
            ( model, intent [ ( "kind", E.string "setTemp" ), ( "value", E.int t ) ] )

        SetMode m ->
            ( model, intent [ ( "kind", E.string "setMode" ), ( "value", E.string m ) ] )

        SetFan f ->
            ( model, intent [ ( "kind", E.string "setFan" ), ( "value", E.string f ) ] )

        Event value ->
            ( applyEvent value model, Cmd.none )


applyEvent : D.Value -> Model -> Model
applyEvent value model =
    case D.decodeValue eventDecoder value of
        Ok ev ->
            case ev of
                StateEv s name ->
                    { model | conn = s, device = name |> orElse model.device, error = Nothing }

                StatusEv st ->
                    { model | status = Just st, conn = Ready }

                ErrorEv m ->
                    { model | error = Just m, conn = if model.conn == Connecting then Disconnected else model.conn }

        Err _ ->
            model


orElse : Maybe a -> Maybe a -> Maybe a
orElse a b =
    case a of
        Just _ -> a
        Nothing -> b


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
        "connecting" -> Connecting
        "login" -> NeedPin
        "ready" -> Ready
        _ -> Disconnected


statusDecoder : D.Decoder Status
statusDecoder =
    D.map6 Status
        (D.field "power" D.bool)
        (D.field "temp" D.int)
        (D.field "mode" D.string)
        (D.field "fan" D.string)
        (D.field "room" D.int)
        (D.field "watts" D.int)



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "wrap" ]
        [ header [] [ h1 [] [ text "A/C" ], span [ class "sub" ] [ text "local BLE control" ] ]
        , case model.error of
            Just e -> div [ class "err" ] [ text e ]
            Nothing -> text ""
        , viewBody model
        , footer [] [ text "No cloud. Talks straight to the AC over Bluetooth." ]
        ]


viewBody : Model -> Html Msg
viewBody model =
    case model.conn of
        Disconnected ->
            div [ class "card center" ]
                [ p [] [ text "Connect to a A/C in Bluetooth range." ]
                , button [ class "primary", onClick Connect ] [ text "Connect" ]
                ]

        Connecting ->
            div [ class "card center" ] [ p [] [ text "Connecting…" ] ]

        NeedPin ->
            div [ class "card center" ]
                [ p [] [ text "Enter the 4-digit passkey (default 0000)." ]
                , input [ type_ "tel", value model.pin, onInput PinChanged, class "pin", attribute "maxlength" "4" ] []
                , button [ class "primary", onClick Login ] [ text "Unlock" ]
                ]

        Ready ->
            viewControls model


viewControls : Model -> Html Msg
viewControls model =
    let
        st =
            Maybe.withDefault (Status False 24 "cool" "auto" 0 0) model.status
    in
    div []
        [ div [ class "card room" ]
            [ div [ class "big" ] [ text (String.fromInt st.room ++ "°") ]
            , div [ class "muted" ] [ text ("room · " ++ String.fromInt st.watts ++ " W") ]
            ]
        , div [ class "card" ]
            [ row "Power"
                [ toggle st.power (SetPower (not st.power)) (if st.power then "On" else "Off") ]
            , row "Set point"
                [ stepper st.temp ]
            , row "Mode"
                [ chips [ "cool", "dry", "fan", "auto", "heat" ] st.mode SetMode ]
            , row "Fan"
                [ chips [ "auto", "low", "medium", "high" ] st.fan SetFan ]
            ]
        , button [ class "ghost", onClick Disconnect ] [ text "Disconnect" ]
        ]


row : String -> List (Html Msg) -> Html Msg
row label controls =
    div [ class "ctl" ] (label_ label :: controls)


label_ : String -> Html Msg
label_ s =
    span [ class "label" ] [ text s ]


toggle : Bool -> Msg -> String -> Html Msg
toggle on msg lbl =
    button [ classList [ ( "sw", True ), ( "on", on ) ], onClick msg ] [ text lbl ]


stepper : Int -> Html Msg
stepper t =
    div [ class "stepper" ]
        [ button [ onClick (SetTemp (Basics.max 16 (t - 1))) ] [ text "−" ]
        , span [ class "val" ] [ text (String.fromInt t ++ "°") ]
        , button [ onClick (SetTemp (Basics.min 30 (t + 1))) ] [ text "+" ]
        ]


chips : List String -> String -> (String -> Msg) -> Html Msg
chips opts current toMsg =
    div [ class "chips" ]
        (List.map
            (\o ->
                button
                    [ classList [ ( "chip", True ), ( "sel", o == current ) ], onClick (toMsg o) ]
                    [ text o ]
            )
            opts
        )



-- MAIN


main : Program () Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , view = view
        , subscriptions = \_ -> bleEvents Event
        }
