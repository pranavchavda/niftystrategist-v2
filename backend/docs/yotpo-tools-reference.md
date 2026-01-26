# Yotpo Tools Reference

Quick reference for the three Yotpo integration tools.

## Overview

Three permanent tools for managing Yotpo reviews and loyalty programs:

1. **`yotpo_check_review.py`** - Check if customers have left reviews
2. **`yotpo_get_loyalty.py`** - View customer loyalty history and points
3. **`yotpo_add_points.py`** - Add or remove customer loyalty points

## Required Environment Variables

All tools require the following environment variables (already configured):

```bash
# Reviews API (yotpo_check_review.py)
YOTPO_APP_KEY=6DQ85qiKjzh6yzsbQ0x58s7cVhN1IySPK6UPhfxt
YOTPO_API_SECRET=otefXuNgtWh9g5HUHnSNxpZLp9r9BJEeSpTI2OXO

# Loyalty API (yotpo_get_loyalty.py, yotpo_add_points.py)
YOTPO_LOYALTY_GUID=Yir-Wf3wNt8_YqON7EvShA
YOTPO_LOYALTY_API_KEY=iY4A1MXFOyDSZPG4SeQrvgtt
```

---

## Tool 1: Check Reviews (`yotpo_check_review.py`)

Check if a customer has left a review on Yotpo.

**IMPORTANT**: The primary method is checking loyalty history for review-related point transactions. This is the MOST RELIABLE way to verify if someone left a review, since Yotpo's Reviews API doesn't expose email addresses in search results without special permissions.

### Basic Usage

```bash
# Check by email (checks loyalty history FIRST)
python tools/yotpo_check_review.py --email customer@example.com

# Skip loyalty check and go straight to review search
python tools/yotpo_check_review.py --email customer@example.com --skip-loyalty

# Search by name
python tools/yotpo_check_review.py --name "John Smith"

# Free text search
python tools/yotpo_check_review.py --search "great espresso machine"

# Get all recent reviews
python tools/yotpo_check_review.py --all --per-page 20
```

### Options

- `--email EMAIL` - Search by customer email (checks loyalty history first)
- `--skip-loyalty` - Skip loyalty history check and search reviews directly
- `--name NAME` - Search by customer name
- `--search TEXT` - Free text search across reviews
- `--all` - Get all reviews (paginated)
- `--per-page N` - Results per page (default: 50)
- `--page N` - Page number (default: 1)
- `--json` - Output raw JSON

### How It Works

When searching by email, the tool uses a two-step approach:

1. **Loyalty History Check** (Primary Method - Most Reliable):
   - Checks customer's loyalty history for review-related point transactions
   - Shows all review activity including dates and points earned
   - **This is the definitive way to verify if someone left a review**

2. **Direct Review Search** (Fallback - Limited):
   - Uses text search across review content and titles
   - **Note**: Does not search by email directly (API limitation)
   - Only works if email appears in review content or customer display name

### Example Output - Loyalty History (Recommended)

```
================================================================================
REVIEW ACTIVITY FOR: customer@example.com
================================================================================

✓ Review with Text
  Points Earned: 300
  Date: 2025-10-01 14:23:45
  Status: Approved

✓ Review with Photo
  Points Earned: 500
  Date: 2025-09-28 10:15:32
  Status: Approved
  Order(s): 12345

================================================================================
Total Review Points Earned: 800
================================================================================
```

### Example Output - Text Search (Fallback)

```
Found 1 review(s) (Total: 1)

================================================================================
Review ID: 123456789
Score: ★★★★★ (5/5)
Customer: John Smith
Email: N/A
User ID: 12345678
Product ID: 7988819067938
SKU: N/A
Date: 2025-10-01T14:23:45.000Z
Verified Buyer: Yes

Title: Amazing espresso machine!

Review: This machine has completely transformed my morning routine.
The build quality is excellent and the espresso is cafe-quality.

Sentiment Score: 0.982
================================================================================
```

### API Limits

- 30,000 requests/minute for search
- 3-hour data retrieval delay

---

## Tool 2: Get Loyalty History (`yotpo_get_loyalty.py`)

View customer loyalty points balance and transaction history.

### Basic Usage

```bash
# Get customer by email (recommended)
python tools/yotpo_get_loyalty.py --email customer@example.com

# Get customer by ID
python tools/yotpo_get_loyalty.py --id 12345678

# Skip history for faster response
python tools/yotpo_get_loyalty.py --email customer@example.com --no-history

# Output as JSON
python tools/yotpo_get_loyalty.py --email customer@example.com --json
```

### Options

- `--email EMAIL` - Customer email address (recommended)
- `--id ID` - Customer ID in Yotpo
- `--no-history` - Skip points history (faster)
- `--no-referral` - Skip referral code
- `--json` - Output raw JSON

### Example Output

```
================================================================================
CUSTOMER LOYALTY SUMMARY
================================================================================

Customer ID: 12345678
Email: customer@example.com
Name: John Smith

────────────────────────────── Points Balance ──────────────────────────────────
Current Points: 1,250
Total Points Earned: 2,500
Points Pending: 50

VIP Tier: Gold

─────────────────────────── Referral Information ───────────────────────────────
Referral Code: JOHN-SMITH-REF
Referral Link: https://idrinkcoffee.com/pages/loyalty?ref=JOHN-SMITH-REF
Total Referrals: 3

──────────────────────────────── Points History ────────────────────────────────

Recent Activity (showing last 10 transactions):

  1. Purchase
     Points: +100
     Date: 2025-10-01 14:23:45
     Status: approved

  2. Review with photo
     Points: +50
     Date: 2025-09-28 10:15:32
     Status: approved

  3. Redeemed for discount
     Points: -500
     Date: 2025-09-25 16:42:18
     Status: approved

────────────────────────── Account Information ────────────────────────────
Created: 2024-01-15 09:30:00
Last Seen: 2025-10-01 14:23:45
Opted In: Yes

================================================================================
```

### API Limits

- 100 requests/minute per app key

---

## Tool 3: Add/Remove Points (`yotpo_add_points.py`)

Add or remove loyalty points for customers with various adjustment types.

### Point Adjustment Types

1. **Reward customer** - Add points and increase total earned
2. **Refund points** - Add points without increasing total earned
3. **Redeem points** - Remove points (for discounts)
4. **Remove earned points** - Remove points and decrease total earned
5. **Expire points** - Remove points without affecting total earned

### Basic Usage

```bash
# Add 100 bonus points (affects total earned)
python tools/yotpo_add_points.py --email customer@example.com --points 100 \
  --reason "Birthday bonus" --note "Happy birthday!"

# Refund 50 points (doesn't affect total earned)
python tools/yotpo_add_points.py --email customer@example.com --points 50 --no-earned \
  --reason "Refund" --note "Order cancelled"

# Remove 25 points (affects total earned)
python tools/yotpo_add_points.py --email customer@example.com --points -25 \
  --reason "Correction" --note "Duplicate points"

# Dry run (preview without changes)
python tools/yotpo_add_points.py --email customer@example.com --points 100 --dry-run
```

### Options

- `--email EMAIL` - Customer email (recommended)
- `--customer-id ID` - Customer ID in Yotpo
- `--points N` - Points to add (positive) or remove (negative)
- `--earned` - Adjust total points earned (default)
- `--no-earned` - Don't adjust total points earned
- `--reason TEXT` - Reason for adjustment
- `--note TEXT` - Optional note
- `--dry-run` - Preview without making changes
- `--json` - Output raw JSON

### Example Output

```
Looking up customer: customer@example.com...
Found customer ID: 12345678

================================================================================
POINTS ADJUSTMENT SUMMARY
================================================================================
Customer ID: 12345678
Email: customer@example.com

Current Balance: 1,250
Total Earned: 2,500

Adding: 100 points
This will affect total points earned

New Balance: 1,350
Reason: Birthday bonus
Note: Happy birthday!
================================================================================

Proceed with points adjustment? (yes/no): yes
Adjusting points...

✓ Points adjustment successful!
New balance: 1,350 points
Total earned: 2,600 points
```

### Safety Features

- Interactive confirmation before applying changes
- Dry-run mode to preview adjustments
- Clear display of current and new balances
- Automatic customer lookup by email

### API Limits

- 100 requests/minute per app key

---

## Common Workflows

### 1. Check if customer left a review and reward them

```bash
# Step 1: Check for review
python tools/yotpo_check_review.py --email customer@example.com

# Step 2: If they left a good review, add bonus points
python tools/yotpo_add_points.py --email customer@example.com --points 50 \
  --reason "Bonus for detailed review" --note "Thanks for the great review!"
```

### 2. Check customer loyalty status before support call

```bash
# Get full customer profile
python tools/yotpo_get_loyalty.py --email customer@example.com
```

### 3. Refund points for cancelled order

```bash
# Refund without affecting total earned
python tools/yotpo_add_points.py --email customer@example.com --points 100 --no-earned \
  --reason "Order refund" --note "Order #12345 cancelled"
```

### 4. Monthly review of top reviewers

```bash
# Get all recent reviews
python tools/yotpo_check_review.py --all --per-page 50 --json > recent_reviews.json

# Analyze and reward top reviewers manually
```

---

## Troubleshooting

### Customer not found

If a customer isn't found in Yotpo Loyalty, they may need to be created first. This typically happens when:
- They've never made a purchase
- They haven't opted into the loyalty program
- There's a typo in the email address

### API rate limits

If you hit rate limits:
- For reviews: Wait a few seconds between requests
- For loyalty: Maximum 100 requests/minute
- Use `--no-history` flag to speed up loyalty lookups when history isn't needed

### Points not updating

Make sure you're using the correct adjustment type:
- Use `--earned` (default) when rewarding customers
- Use `--no-earned` when refunding or expiring points

---

## API Documentation

Official Yotpo API documentation:
- Reviews API: https://apidocs.yotpo.com/reference/welcome
- Loyalty API: https://loyaltyapi.yotpo.com/reference/reference-getting-started
- API Authentication: https://support.yotpo.com/docs/yotpo-api

---

Last updated: 2025-10-08
