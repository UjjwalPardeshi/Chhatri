"""Conversation with merchants in Hindi + English (SPEC §13, §24.4).

Modules: ``messages`` (catalogue), ``lexicon`` + ``intents`` (rule classifier), ``nlu`` (optional
LLM), ``guard`` (free-text guard), ``ports`` (ClaimsPort and store slices), ``outbox`` (the one
send/record path), ``replies`` / ``slip_flow`` (inbound flows), ``notifications``
(business-initiated flows), ``reasons`` (which text explains a decision) and ``service``
(``ConversationService``).
"""
