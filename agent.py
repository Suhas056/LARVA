import argparse

from ollama import chat

from app_launcher import APP_PATHS, detect_open_command, open_application
from config import MODEL
from voice import listen_for_command, wait_for_wake_word


available_functions = {
    "open_application": open_application,
}

tools = [
    open_application,
]

chat_history = [
    {
        "role": "system",
        "content": """
You are LARVA, a local AI assistant running on Windows.

You have an open_application tool.

When the user asks you to open or launch an application,
use the tool with the application name provided by the user.

Do not claim an application opened unless the tool result
confirms that it opened successfully.

If the tool cannot find an application, explain that honestly.
""",
    }
]


def main(text_mode: bool = False) -> None:
    print("================================")
    print("          LARVA ONLINE")
    print("================================")
    print(f"Discovered {len(APP_PATHS)} Start Menu shortcuts.")
    if text_mode:
        print("Text mode enabled. Type 'exit' to stop.\n")
    else:
        print("Say 'Hey Jarvis' to give a command. Press Ctrl+C to stop.\n")

    while True:
        if text_mode:
            user_input = input("You: ").strip()
        else:
            if not wait_for_wake_word():
                break
            print("LARVA: Please speak a command.")
            user_input = listen_for_command()

        if not user_input:
            continue

        if user_input.lower() == "exit":
            print("LARVA: Goodbye.")
            break

        detected_app = detect_open_command(user_input)
        if detected_app:
            print(f"\n[LARVA detected an app request: {detected_app}]")
            result = open_application(detected_app)
            print(f"[Result: {result}]\n")

            chat_history.append({
                "role": "user",
                "content": user_input,
            })
            chat_history.append({
                "role": "assistant",
                "content": result,
            })
            continue

        chat_history.append({
            "role": "user",
            "content": user_input,
        })

        try:
            while True:
                response = chat(
                    model=MODEL,
                    messages=chat_history,
                    tools=tools,
                )
                chat_history.append(response.message)

                if response.message.tool_calls:
                    for tool_call in response.message.tool_calls:
                        function_name = tool_call.function.name
                        arguments = tool_call.function.arguments

                        print(f"\n[Tool: {function_name}]")
                        print(f"[Arguments: {arguments}]")

                        if function_name in available_functions:
                            function_to_call = available_functions[function_name]
                            result = function_to_call(**arguments)
                        else:
                            result = "Unknown tool."

                        print(f"[Result: {result}]\n")
                        chat_history.append({
                            "role": "tool",
                            "tool_name": function_name,
                            "content": str(result),
                        })

                    continue

                print(f"LARVA: {response.message.content}\n")
                break

        except Exception as error:
            print(f"\nError: {error}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the LARVA assistant.")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Use keyboard input instead of always-listening voice mode.",
    )
    main(text_mode=parser.parse_args().text)
