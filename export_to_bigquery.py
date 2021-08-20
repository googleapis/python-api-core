from google.cloud import contact_center_insights_v1


project_id = "busun-sandbox"
bigquery_project_id = "busun-sandbox"
bigquery_table = "ccai-table"
bigquery_dataset = "test"

request = contact_center_insights_v1.ExportInsightsDataRequest()

request.parent = contact_center_insights_v1.ContactCenterInsightsClient.common_location_path(project_id, "us-central1")
request.big_query_destination.project_id = bigquery_project_id
request.big_query_destination.table = bigquery_table
request.big_query_destination.dataset = bigquery_dataset

print(request)

# Call the Insights client to export data to BigQuery.
insights_client = contact_center_insights_v1.ContactCenterInsightsClient()
export_operation = insights_client.export_insights_data(request=request)

print("Waiting for results...")
result = export_operation.result(500)
print(result)
