# Chatwoot HITL Loop Blueprint

## Summary

The first live preview connects a Chatwoot inbox to Agent Studio and the Sagad OS Console. It proves the full loop without allowing autonomous live replies.

![Chatwoot HITL Poster](images/chatwoot-hitl-poster.png)

## Flow

```mermaid
sequenceDiagram
  participant C as Customer
  participant CW as Chatwoot
  participant AS as Agent Studio
  participant KB as Knowledge Pack
  participant UI as Sagad OS Console
  participant S as Supervisor

  C->>CW: Sends website chat message
  CW->>AS: Webhook payload
  AS->>AS: Normalize and classify
  AS->>KB: Retrieve KB/SOP/QA/compliance context
  KB-->>AS: Cited context pack
  AS->>AS: Draft reply and run QA/compliance
  AS-->>UI: Conversation appears in approval queue
  S->>UI: Approves or edits reply
  UI->>AS: Approve-send request
  AS->>CW: Send approved message
  CW-->>C: Customer receives approved reply
```

![Chatwoot HITL Diagram](images/chatwoot-hitl-loop.png)

## Safety Rules

- The backend receives real Chatwoot messages.
- The AI can draft and recommend actions.
- Only HITL-approved replies can be sent.
- If Chatwoot send fails, the conversation remains visible with failed send status.
- If knowledge retrieval fails, the draft must use a safe fallback and require review.
