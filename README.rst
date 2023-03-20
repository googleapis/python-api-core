First create and enable a python virtual env.

```
pyenv virtualenv metric_test
pyenv local metric_test
```

Next modify the metadata we want to send. Open `google/api_core/gapic_v1/method.py`,
at the end of the file before the return statement, set your `user_agent_metadata`.

Next install libs, 
```
python -m pip install -e .
python -m pip install google-cloud-kms
python -m pip install google-cloud-compute
```

Next go to the `metric_sample` folder, open `compute.py` and `kms.py`,
and change the project to your project.

Run the samples and save the log.

kms is grpc GAPIC client, we send two x-goog-api-client headers:
```
GRPC_VERBOSITY=debug GRPC_TRACE=http,api python kms.py >& kms.log
```

compute is http GAPIC client, we try to send both x-goog-api-client and user-agent to simulate gcloud call:
```
python compute.py >& compute.log
```

Then open the logs, search for `x-goog-api-client` and `user-agent` headers.

