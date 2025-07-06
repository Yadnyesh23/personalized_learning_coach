# Streaming RAG Answer API

## Endpoint
`POST /session/{session_id}/rag/stream/`

## Description
Provides real-time streaming responses using RAG (Retrieval-Augmented Generation) with automatic memory extraction and goal tracking.

## Request

### Headers
- `Content-Type: application/json`

### Body
```json
{
  "query": "Your question here"
}
```

## Response

### Format
Server-Sent Events (SSE) stream with `Content-Type: text/event-stream`

### Response Structure

**Streaming Chunks:**
```
data: {"chunk": "Hello", "done": false}
data: {"chunk": " world", "done": false}
```

**Final Chunk:**
```
data: {
  "chunk": "",
  "done": true,
  "metadata": {
    "goals_created": [
      {
        "id": 1,
        "title": "Learn Python",
        "description": "Master Python fundamentals",
        "deadline": "2024-06-01T00:00:00",
        "status": "pending"
      }
    ],
    "memory_saved": true,
    "memory_content": "User prefers visual learning"
  }
}
```

## Features

- **Real-time streaming**: Get responses as they're generated
- **RAG Integration**: Uses uploaded PDFs for context
- **Memory Extraction**: Automatically saves learning preferences
- **Goal Tracking**: Extracts and creates goals from conversation
- **Session Context**: Maintains conversation history
- **Metadata Response**: Returns info about goals created and memory saved

## Error Response
```
data: {"chunk": "", "done": true, "error": "Error message"}
```

## Usage Example

```javascript
const eventSource = new EventSource('/session/123/rag/stream/', {
  method: 'POST',
  body: JSON.stringify({ query: "Explain machine learning" })
});

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  if (data.done) {
    if (data.metadata) {
      console.log('Goals created:', data.metadata.goals_created);
      console.log('Memory saved:', data.metadata.memory_saved);
    }
  } else {
    console.log(data.chunk); // Stream content
  }
};
``` 