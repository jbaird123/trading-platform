# TradingView Strategy Properties Check

## Issue Found

Your export shows TradingView is executing at **next bar close** instead of **next bar open**.

**Evidence:**
- Crossover detected: 2023-01-06 14:00 EST close
- Should execute at: 15:00 EST **open** = 1.06456
- Actually executing at: 15:00 EST **close** = 1.06463

Even though our script has `process_orders_on_close=false`, TradingView is behaving as if it's set to `true`.

## Root Cause

The TradingView **Properties tab** can **override script settings**!

## How to Fix

### 1. Click on Strategy Settings

In TradingView:
1. Make sure the strategy is loaded on your chart
2. Click on the strategy name at the top of the chart
3. Click the **gear icon** (⚙️) or right-click → "Settings..."

### 2. Go to Properties Tab

In the settings dialog:
1. Click on the **"Properties"** tab (not "Inputs" or "Style")
2. Scroll down to find order execution settings

### 3. Find "Verify Price for Limit Orders" Section

Look for a section related to order fills or execution. There should be an option called:
- **"Recalculate: On every order fill"**
- **"On bar close"** (checkbox)

### 4. Uncheck "On bar close"

- [ ] **On bar close** ← This should be **UNCHECKED**

If this box is checked, it overrides your script's `process_orders_on_close=false` setting!

### 5. Alternative: Check for "Do not use standard OHLC"

There may also be an option like:
- **"Do not use standard OHLC"** or
- **"Fill orders on..."**

Make sure it's set to use standard OHLC bars (not synthetic prices).

### 6. Save and Re-Export

After unchecking "On bar close":
1. Click "OK" to save settings
2. The strategy will recalculate
3. Check if first trade entry price changed to **1.06456**
4. If yes, re-export both trades.csv and OHLCV data

## Expected Result

After unchecking "On bar close":
- First trade entry should be **1.06456** (not 1.06463)
- This will be the 15:00 EST bar **open** price
- Much more realistic execution model

## If Settings Look Correct

If "On bar close" is already unchecked and you're still getting 1.06463:

**Option A:** TradingView may have changed default behavior in recent versions

**Option B:** We accept this execution model and update our platform to match
- Our platform currently: current bar close
- TradingView currently: next bar close
- Both should use: next bar open (but TV may not support this)

Let me know what you find in the Properties tab!

## Screenshot Request

If possible, take a screenshot of the Properties tab so I can see all available options. This will help us understand what TradingView actually supports.
