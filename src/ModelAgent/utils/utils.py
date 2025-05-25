def form_message(system, user):
    return [
        {
            "role": "system",
            "content": system
        },
        {
            "role": "user",
            "content": user
        }
    ]

