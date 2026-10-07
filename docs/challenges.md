# CHALLENGES

Running log: symptom, root cause, fix, lesson. Newest at the bottom.

## C-001: kubectl "connection refused" after Docker Desktop restart (2026-10-03)
- Symptom: kubectl -> connectex refused on 127.0.0.1:<random port>, though context, kubeconfig and containers looked fine.
- Cause: kind publishes the API server on a random host port stored in kubeconfig. Docker Desktop restarted and the mapping was lost (docker ps showed 6443/tcp with no host port).
- Fix: started the existing socat proxy container and ran `kubectl config set-cluster <ctx> --server=https://127.0.0.1:16443`.
- Lesson: compare the docker ps port column with the kubeconfig server. Fixed permanently in the new cluster with `apiServerPort: 6550` in kind-config.yaml. `kind export kubeconfig` overwrites manual edits.

## C-002: Git Bash rewrites Linux paths in docker/kubectl exec (2026-10-03)
- Symptom: `--kubeconfig=/etc/kubernetes/admin.conf` became `C:/Program Files/Git/etc/...`.
- Cause: MSYS path conversion.
- Fix: prefix with `MSYS_NO_PATHCONV=1` or use a double slash.
- Lesson: applies to every exec with an absolute path from Git Bash.

## C-003: kubectl falls back to localhost:8080 after deleting the only cluster (2026-10-03)
- Symptom: `Get "http://localhost:8080/api": EOF` after `kind delete cluster`.
- Cause: the delete removed the context, leaving no current-context, so kubectl uses its default address. A stale context (adam) was also left over.
- Fix: removed stale entries with `kubectl config delete-context`, `delete-cluster`, `unset users.<name>`.
- Lesson: empty get-contexts between clusters is expected. 8080 here is kubectl's default, not a service.

## C-004: Host ports 8080/8443 clash between kind clusters (2026-10-03)
- Cause: old Task Tracker cluster held the ports this project maps for the Gateway.
- Fix: deleted that cluster before creating the fraud cluster.
- Lesson: one kind cluster per host port.

## C-005: Calico v3.32 Helm install fails "no matches for kind Installation" (2026-10-04)
- Cause: from v3.32 the tigera-operator chart no longer bundles CRDs.
- Fix: `helm template calico-crds projectcalico/crd.projectcalico.org.v1 --version v3.32.2 | kubectl apply --server-side -f -`, then the normal helm install.
- Lesson: "ensure CRDs are installed first" means the API types don't exist yet. Check the chart README for version-specific steps.

## C-006: kubectl rejects helm template output from an OCI chart (2026-10-04)
- Symptom: `error validating "STDIN": [apiVersion not set, kind not set]`.
- Cause: Helm prints `Pulled:` and `Digest:` lines to stdout when downloading an OCI chart, and they were piped into kubectl.
- Fix: `tail -n +3`, or `helm pull` first and template from the local .tgz.
- Lesson: redirect to a file and read the first lines before guessing.

## C-007: Envoy Gateway Helm install does not create a GatewayClass (2026-10-04)
- Symptom: `kubectl get gatewayclass` -> No resources found, though the guide said it is automatic.
- Cause: the chart installs the controller and CRDs only. The quickstart manifest creates the class.
- Fix: applied our own k8s/gatewayclass.yaml with controllerName gateway.envoyproxy.io/gatewayclass-controller.
- Lesson: a running controller does nothing until a GatewayClass binds it. Verify "created automatically" claims.

## C-008: Guide's Strimzi snippet used a superseded API version (2026-10-04)
- Finding: guide uses kafka.strimzi.io/v1beta2. Current Strimzi uses the stable v1 API. Used v1 and the official single-node KRaft example as the base.
- Lesson: operator CRD versions drift between releases. Check the docs for the installed version before copying manifests.