from __future__ import annotations

from textwrap import dedent

from app.models import Workload


def render_deployment(workload: Workload) -> str:
    """Produit le Deployment Kubernetes d'une charge (pod template inclus)."""
    return dedent(
        f"""\
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: {workload.name}
          namespace: {workload.namespace}
          labels:
            app.kubernetes.io/name: {workload.name}
            openyard.io/managed: "true"
        spec:
          replicas: {workload.replicas}
          selector:
            matchLabels:
              app.kubernetes.io/name: {workload.name}
          template:
            metadata:
              labels:
                app.kubernetes.io/name: {workload.name}
                openyard.io/managed: "true"
            spec:
              automountServiceAccountToken: false
              securityContext:
                runAsNonRoot: true
                runAsUser: 10001
                runAsGroup: 10001
                fsGroup: 10001
                seccompProfile:
                  type: RuntimeDefault
              containers:
                - name: app
                  image: {workload.image}
                  imagePullPolicy: IfNotPresent
                  ports:
                    - name: http
                      containerPort: {workload.port}
                  securityContext:
                    allowPrivilegeEscalation: false
                    readOnlyRootFilesystem: true
                    capabilities:
                      drop: ["ALL"]
                  resources:
                    requests:
                      cpu: {workload.cpu}
                      memory: {workload.memory}
                    limits:
                      cpu: {workload.cpu}
                      memory: {workload.memory}
                  volumeMounts:
                    - name: tmp
                      mountPath: /tmp
              volumes:
                - name: tmp
                  emptyDir: {{}}
        """
    )


def render_service(workload: Workload) -> str:
    return dedent(
        f"""\
        apiVersion: v1
        kind: Service
        metadata:
          name: {workload.name}
          namespace: {workload.namespace}
          labels:
            app.kubernetes.io/name: {workload.name}
            openyard.io/managed: "true"
        spec:
          selector:
            app.kubernetes.io/name: {workload.name}
          ports:
            - name: http
              port: 80
              targetPort: http
        """
    )


def render_bundle(workload: Workload) -> str:
    return f"{render_deployment(workload).rstrip()}\n---\n{render_service(workload)}"
