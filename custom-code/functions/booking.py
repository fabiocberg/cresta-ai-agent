import asyncio
import json

from cresta.agent.sdk.functions import tool
from cresta.agent.sdk.secrets import get_secret
from cresta.agent.sdk.types import FunctionInput, FunctionOutput, FunctionOutputGenerator
from cresta.agent.types.types import AIAgentAction, GenerateAgain
from cresta.agent.sdk.context.context import Context

from marina.cresta_transport import CrestaTransport
from marina.flight_api import FlightAPI, failure
from marina.session import BookingSession


async def execute(input, operation, *args):
    try:
        key = "" if Context.get_context("mock_config") is not None else get_secret("FLIGHT_API_KEY")
    except (KeyError, RuntimeError):
        return FunctionOutput(tool_msg=json.dumps(failure("configuration_error")),
                              action=AIAgentAction(generate_again=GenerateAgain.YES))
    session = BookingSession(FlightAPI(CrestaTransport(
        key, replay_loop=asyncio.get_running_loop())), input.variables)
    result = await asyncio.to_thread(getattr(session, operation), *args)
    return FunctionOutput(tool_msg=json.dumps(result, allow_nan=False), variables=session.variables(),
                          action=AIAgentAction(generate_again=GenerateAgain.YES))


@tool.function("search_flights", description="Search available flights using all four confirmed search fields.", strict=True)
async def search_flights(input: FunctionInput, origin: str, destination: str,
                         departure_date: str, passengers: int) -> FunctionOutputGenerator:
    yield await execute(input, "search", origin, destination, departure_date, passengers)


@tool.function("save_passenger_information", description="Save all five passenger fields after selecting a flight from the current search. Returns a verified passenger ID.", strict=True)
async def save_passenger_information(input: FunctionInput, flight_id: str, first_name: str,
                                     last_name: str, email: str, phone: str,
                                     date_of_birth: str) -> FunctionOutputGenerator:
    yield await execute(input, "save", flight_id, first_name, last_name, email, phone, date_of_birth)


@tool.function("book_flight", description="Complete one individual booking using verified returned IDs. Set confirmed=true only after the caller explicitly agrees to these exact details. Never call on deferral or a human request.", strict=True)
async def book_flight(input: FunctionInput, passenger_id: str, flight_id: str,
                      seat_preference: str, confirmed: bool) -> FunctionOutputGenerator:
    yield await execute(input, "book", passenger_id, flight_id, seat_preference, confirmed)
