import type { Dictionary } from "./ru";

export const en: Dictionary = {
  nav: {
    rooms: "Rooms",
    about: "About",
    tour: "3D tour",
    location: "Location",
    payment: "Payment",
    contacts: "Contacts",
    book: "Book now",
    openMenu: "Open menu",
    closeMenu: "Close menu",
    toContent: "Skip to content",
    home: "home page",
    language: "Language",
  },

  common: {
    perNight: "per night",
    from: "from",
    guests: "guests",
    guestsOne: "guest",
    upTo: "up to",
    more: "Details",
    call: "Call us",
    writeWhatsApp: "Message on WhatsApp",
    bookRoom: "Book a room",
    leaveRequest: "Send a request",
    bookOnline: "Book online",
    breakfastIncluded: "Breakfast included",
    checkIn: "Check-in",
    checkOut: "Check-out",
    area: "Size",
    beds: "Beds",
    allRooms: "All rooms",
  },

  hero: {
    titleTop: "A hotel in central Almaty",
    titleBottom: "where you'll want to stay longer",
    lead: "{count} rooms a short walk from Abay Avenue. Breakfast included, check-in around the clock. From {price} per night.",
    factRooms: "rooms",
    factReception: "front desk",
    factBreakfast: "breakfast included",
  },

  booking: {
    checkIn: "Check-in",
    checkOut: "Check-out",
    guests: "Guests",
    roomType: "Room type",
    anyRoom: "Any",
    search: "Find a room",
    pickForMe: "Choose for me",
    title: "Book a room",
    titleWithRoom: "Booking: {room}",
    leadWithRoom: "{area}, up to {capacity} guests, {price} per night. Breakfast included.",
    lead: "Send a request and we'll match a room to your dates and confirm the booking. Rooms from {price} per night, breakfast included.",
    fasterByPhone: "Faster by phone",
    fasterByPhoneText:
      "The front desk answers around the clock. Booking by phone takes a couple of minutes.",
    conditions: "Conditions",
    payment: "Payment",
    children: "Children",
    form: {
      checkInDate: "Check-in date",
      checkOutDate: "Check-out date",
      roomType: "Room type",
      guestCount: "Number of guests",
      name: "Name",
      namePlaceholder: "How should we address you",
      phone: "Phone",
      email: "Email",
      emailOptional: "(optional)",
      emailPlaceholder: "We'll send the booking confirmation",
      comment: "Comment",
      commentPlaceholder: "Early check-in, invoice for a company, higher floor — write here",
      submit: "Send request",
      submitting: "Sending…",
      consent: "By clicking the button you agree to the",
      consentLink: "privacy policy",
      sentTitle: "Request sent",
      sentText:
        "We'll get back to you within 15 minutes during working hours and confirm the booking. If you need it sooner, message us on WhatsApp.",
      errorPrefix: "The request could not be sent",
      errorSuffix: "Please call",
      errorOr: "or",
      errorWhatsApp: "send the request via WhatsApp",
    },
  },

  about: {
    eyebrow: "About the hotel",
    titleTop: "{count} rooms, one principle:",
    titleAccent: "everything is already included",
    description:
      "Airis Residence is a small city hotel where you don't pay extra for the obvious. Fast Wi-Fi, quiet, breakfast and a 24-hour front desk are part of the room rate.",
    points: [
      {
        title: "Central, but quiet",
        text: "Nauryzbai Batyr 134/2 — 800 metres to Abay Avenue and 700 to Baikonur metro station. The courtyard is enclosed and the windows don't face the road.",
      },
      {
        title: "Check in at any hour",
        text: "The front desk works around the clock. Arrived on a night flight? You'll be checked in with no late-arrival surcharge.",
      },
      {
        title: "Breakfast is in the rate",
        text: "A buffet every morning: hot dishes, pastries, fruit and cheese. No need to look for a café or count a separate bill.",
      },
    ],
  },

  rooms: {
    eyebrow: "Rooms",
    title: "{count} room types — from compact to suite",
    description:
      "Every room has air conditioning, a safe, a minibar and a private bathroom. Breakfast is included in every rate.",
    pageTitle: "Rooms at Airis Residence",
    pageLead:
      "{count} room types. Each has air conditioning, a safe, a minibar, a work area and a private bathroom. Breakfast is included in every rate.",
    sectionEquipment: "Room amenities",
    otherRooms: "Other rooms",
    cost: "rate per night",
    bookAria: "Book {room}",
  },

  amenities: {
    eyebrow: "What's included",
    title: "Hotel services",
    description: "No hidden fees: everything listed is part of the room rate.",
    items: [
      { title: "Breakfast included", note: "Buffet every morning" },
      { title: "24/7 front desk", note: "Check in at any hour" },
      { title: "Wi-Fi throughout", note: "Free and unlimited" },
      { title: "Air conditioning in every room", note: "Individual control" },
      { title: "Safe and minibar", note: "In every room" },
      { title: "Card payment", note: "Visa, Mastercard, bank transfer for companies" },
      { title: "Daily housekeeping", note: "Linen changed on schedule" },
      { title: "Transfer and taxi", note: "Arranged on request" },
    ],
  },

  gallery: {
    eyebrow: "Gallery",
    title: "What the hotel looks like",
    hintSwipe: "swipe sideways →",
    hintScroll: "scroll down →",
    alt: "Hotel gallery",
    captions: {
      lobby: "Lobby",
      luxe: "Luxe · 30 m²",
      breakfast: "Breakfast included",
      bath: "Bathroom",
      twin: "Standart Twin",
      details: "Details",
      comfort: "Comfort · 25 m²",
    },
  },

  tour: {
    eyebrow: "3D tour",
    title: "Walk through the hotel before you arrive",
    description:
      "A panoramic tour of the lobby, corridors and rooms — look around in 360° and choose your room with confidence.",
    soon: "The 3D tour is coming soon",
    soonText:
      "The space for the panoramic tour is ready. As soon as the shoot is done, the tour will drop in here without rebuilding the site.",
    loading: "Loading the tour…",
  },

  location: {
    eyebrow: "Location",
    title: "Almaly district, 800 m to Abay Avenue",
    description:
      "The hotel sits in a quiet spot, but everything you need is close: metro, theatres, museums and the city's business district.",
    nearby: "Nearby",
    district: "Almaly district",
    pageTitle: "How to find us",
    pageLead:
      "The hotel is in the Almaly district of Almaty. The front desk works around the clock — call at any time.",
    places: [
      "Baikonur metro station",
      "Abay Avenue",
      "Kazakh National Opera and Ballet Theatre",
      "National Museum of Arts of Kazakhstan",
      "Mukhtar Auezov Theatre",
      "Almaty Airport",
    ],
  },

  faq: {
    eyebrow: "Questions",
    title: "Frequently asked questions",
    items: [
      {
        q: "What are the check-in and check-out times?",
        a: "Check-in from 14:00, check-out by 12:00. The front desk works around the clock, so you can check in at night too. Early check-in and late check-out are available on request, subject to availability.",
      },
      {
        q: "Is breakfast included?",
        a: "Yes, breakfast is included in every room rate. It's a buffet: hot dishes, pastries, cold cuts, fruit and drinks.",
      },
      {
        q: "How can I pay for my stay?",
        a: "We accept cash, Visa and Mastercard, and bank transfer for companies against a contract and invoice. Card payment is available at the front desk and online when booking.",
      },
      {
        q: "Is there parking?",
        a: "There are parking spaces next to the hotel. Please check availability when booking by calling +7 (777) 531-00-09.",
      },
      {
        q: "Are pets allowed?",
        a: "Unfortunately, we cannot accommodate pets.",
      },
      {
        q: "Do you work with companies?",
        a: "Yes. We prepare a contract, an invoice and all closing documents. The details of INCOME HOUSE LLP are in the site footer; we issue the invoice by email on the same day.",
      },
    ],
  },

  cta: {
    eyebrow: "Booking",
    titleTop: "Book direct —",
    titleAccent: "better value than booking sites",
    text: "No agency commission on the official website. Rooms from {price} per night, breakfast included. We confirm bookings within 15 minutes during working hours.",
  },

  footer: {
    tagline:
      "A {count}-room hotel in central Almaty. Breakfast included, front desk open around the clock.",
    rooms: "Rooms",
    info: "Information",
    contacts: "Contacts",
    company: "About the company",
    payment: "How to pay",
    offer: "Public offer",
    privacy: "Privacy policy",
  },

  notFound: {
    eyebrow: "Error 404",
    title: "This page doesn't exist",
    text: "The page may have moved or the address contains a typo. Go back to the home page or take a look at our rooms.",
    home: "Home page",
    rooms: "View rooms",
  },

  legal: {
    translationNoticeTitle: "This document is provided in Russian",
    translationNotice:
      "The legally binding version of this document is written in Russian. A translation can be provided on request.",
  },

  meta: {
    homeTitle: "Airis Residence — hotel in central Almaty | Official website",
    homeDescription:
      "Airis Residence hotel in central Almaty: {count} rooms, breakfast included, 24/7 front desk. Nauryzbai Batyr St. 134/2. Rooms from {price} per night — book direct with no agency commission.",
    roomsTitle: "Rooms at Airis Residence in Almaty — from {price}",
    roomsDescription:
      "Five room types at Airis Residence: from 16 to 30 m², breakfast included, rates from {price} per night.",
    bookingTitle: "Book a room at Airis Residence, Almaty",
    bookingDescription:
      "Book a room at Airis Residence direct: no agency commission, breakfast included, booking confirmed within 15 minutes.",
    contactsTitle: "Contacts — Airis Residence hotel in Almaty",
    contactsDescription:
      "Address: Almaty, Nauryzbai Batyr St. 134/2. Phone +7 (777) 531-00-09 and +7 (727) 277-20-20. Front desk open around the clock.",
  },
};
