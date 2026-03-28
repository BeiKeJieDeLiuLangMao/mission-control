# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]: Self-host mode
        - img [ref=e8]
      - generic [ref=e11]:
        - heading "Local Authentication" [level=1] [ref=e12]
        - paragraph [ref=e13]: Enter your access token to unlock Mission Control.
    - generic [ref=e15]:
      - generic [ref=e16]:
        - text: Access token
        - textbox "Access token" [ref=e17]:
          - /placeholder: Paste token
          - text: 3e7e63bd8bd5267f0a72b4f90dee3a2e96f7689254248f91c4371667451c9178
      - paragraph [ref=e18]: Unable to reach backend to validate token.
      - button "Continue" [ref=e19] [cursor=pointer]
  - button "Open Next.js Dev Tools" [ref=e25] [cursor=pointer]:
    - img [ref=e26]
  - alert [ref=e29]
```