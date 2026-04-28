import base64
import json

# Placeholder credentials (for demonstration)
CLICK_SERVICE_ID = "12345"
CLICK_MERCHANT_ID = "67890"
PAYME_MERCHANT_ID = "5f2c3d..."

def generate_click_link(amount, order_id):
    """
    Generates a Click payment link.
    URL: https://my.click.uz/services/pay?service_id={SERVICE_ID}&merchant_id={MERCHANT_ID}&amount={amount}&transaction_param={order_id}
    """
    return f"https://my.click.uz/services/pay?service_id={CLICK_SERVICE_ID}&merchant_id={CLICK_MERCHANT_ID}&amount={amount}&transaction_param={order_id}"

def generate_payme_link(amount, order_id):
    """
    Generates a Payme payment link with base64 encoded parameters.
    URL: https://checkout.paycom.uz/{base64_encoded_params}
    """
    # Payme expects parameters in a specific format (m=merchant_id;ac.order_id=order_id;a=amount_in_tiyin)
    # Amount in Payme is in tiyin (1 UZS = 100 tiyin)
    amount_tiyin = int(float(amount) * 100)
    params = f"m={PAYME_MERCHANT_ID};ac.order_id={order_id};a={amount_tiyin}"
    
    # Base64 encode the params string
    encoded_params = base64.b64encode(params.encode('utf-8')).decode('utf-8')
    
    return f"https://checkout.paycom.uz/{encoded_params}"
