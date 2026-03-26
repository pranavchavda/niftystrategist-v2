# nf-profile — User Profile & Active Segments

View Upstox account profile, active trading segments, and enabled exchanges.

## Usage

```bash
nf-profile [--json]
```

Shows: User name, email, user ID, broker, active segments (equity, F&O, commodity), enabled exchanges (NSE, BSE, MCX), POA/DDPI status.

## When to use
- **Account verification**: Check which segments/exchanges are enabled
- **Debugging**: Verify the correct Upstox account is connected
- **F&O eligibility**: Check if F&O segment is active before options trading
