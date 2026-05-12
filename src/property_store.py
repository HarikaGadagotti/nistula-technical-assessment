PROPERTY_DATA = {
    "villa-b1": {
        "name": "Villa B1",
        "location": "Assagao, North Goa",
        "bedrooms": 3,
        "max_guests": 6,
        "private_pool": True,
        "checkin": "2 PM",
        "checkout": "11 AM",
        "base_rate": "INR 18,000 per night (up to 4 guests)",
        "extra_guest": "INR 2,000 per night per person",
        "wifi": "Nistula@2024",
        "caretaker": "Available 8 AM – 10 PM",
        "chef": "Yes (24-hour pre-booking required)",
        "availability": "Available April 20–24",
        "cancellation": "Free up to 7 days before check-in",
    }
}


def get_property_context(property_id: str) -> dict:
    return PROPERTY_DATA.get(property_id, PROPERTY_DATA["villa-b1"])