from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)  # This will allow requests from any origin

@app.route('/search', methods=['GET'])
def search_dsld():
    query = request.args.get('product_name', '')
    size = request.args.get('size', '100') # Default to 100 results
    from_val = request.args.get('from', '0') # Default to starting from the beginning

    # Construct a query that requires all terms to be present
    search_terms = query.split()
    if not search_terms:
        q_param = '*'
    else:
        q_param = " AND ".join(search_terms)

    base_url = "https://api.ods.od.nih.gov/dsld/v9/search-filter/"
    params = {
        'q': q_param,
        'product_type': 'a1325',
        'supplement_form': 'e0162',
        'size': size,
        'from': from_val
    }
    print(f"Proxying SEARCH request to: {base_url} with params: {params}")
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/product/<product_id>', methods=['GET'])
def get_product(product_id):
    if not product_id:
        return jsonify({"error": "No product ID provided"}), 400

    base_url = f"https://api.ods.od.nih.gov/dsld/v9/product/{product_id}"
    print(f"Proxying PRODUCT request to: {base_url}")
    try:
        response = requests.get(base_url) # No params needed here
        response.raise_for_status()  # Raise an exception for bad status codes
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route('/label/<label_id>', methods=['GET'])
def get_label(label_id):
    if not label_id:
        return jsonify({"error": "No label ID provided"}), 400

    base_url = f"https://api.ods.od.nih.gov/dsld/v9/label/{label_id}"
    print(f"Proxying LABEL request to: {base_url}")
    try:
        response = requests.get(base_url)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
