targetScope = 'resourceGroup'

param location string = 'westus3'
@minLength(3)
@maxLength(16)
param namePrefix string = 'gmg-agent'
param storageAccountName string
param runtimeIdentityName string

@description('Private registry image reference with an immutable SHA-256 digest.')
param webImage string
@description('Private registry image reference with an immutable SHA-256 digest.')
param apiImage string
@description('Use the loginServer output of registry.bicep for managed-identity pulls.')
param registryServer string = 'ghcr.io'
param registryUsername string = ''
@secure()
param registryPullToken string = ''
param linkedinClientId string
@secure()
param linkedinClientSecret string
@secure()
@description('Retains the previous revision’s pilot allowlist for rollback when supplied.')
param approvedLinkedInEmails string = ''
@secure()
param nextAuthSecret string
@secure()
param internalApiToken string

@description('East US Microsoft Foundry account endpoint.')
param foundryEndpoint string
@description('UTC deadline before the verified nonprofit grant expiry. An empty value keeps inference paused.')
param inferenceAuthorizedUntil string = ''
@minValue(0)
@maxValue(200)
param dailyCalls int = 0
@minValue(0)
@maxValue(6000)
param monthlyCalls int = 0

param whatsappEnabled bool = false
param whatsappPhoneNumberId string = ''
@secure()
param whatsappAppSecret string = ''
@secure()
param whatsappVerifyToken string = ''
@secure()
param whatsappAccessToken string = ''
@secure()
param whatsappTesters string = ''
@minValue(1)
@maxValue(200)
param whatsappMonthlyLimit int = 100

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: runtimeIdentityName
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

var apiUrl = 'http://127.0.0.1:8000/api'
var azureRegistry = endsWith(registryServer, '.azurecr.io')
var registrySecrets = azureRegistry ? [] : [{ name: 'registry-token', value: registryPullToken }]
var whatsappSecrets = whatsappEnabled ? [
  { name: 'whatsapp-app-secret', value: whatsappAppSecret }
  { name: 'whatsapp-verify-token', value: whatsappVerifyToken }
  { name: 'whatsapp-access-token', value: whatsappAccessToken }
  { name: 'whatsapp-testers', value: whatsappTesters }
] : []
var startupProbe = {
  type: 'Startup'
  httpGet: {
    port: 3000
    path: '/api/ready'
  }
  periodSeconds: 5
  timeoutSeconds: 10
  failureThreshold: 24
}
var readinessProbe = {
  type: 'Readiness'
  httpGet: startupProbe.httpGet
  periodSeconds: 3
  timeoutSeconds: 9
  failureThreshold: 10
}
var livenessProbe = {
  type: 'Liveness'
  tcpSocket: {
    port: 3000
  }
  periodSeconds: 10
  failureThreshold: 3
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: namePrefix
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      maxInactiveRevisions: 5
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 3000
        transport: 'auto'
      }
      registries: azureRegistry ? [
        { server: registryServer, identity: identity.id }
      ] : [
        { server: registryServer, username: registryUsername, passwordSecretRef: 'registry-token' }
      ]
      secrets: concat(registrySecrets, whatsappSecrets, empty(approvedLinkedInEmails) ? [] : [
        { name: 'approved-linkedin-emails', value: approvedLinkedInEmails }
      ], [
        { name: 'linkedin-client-secret', value: linkedinClientSecret }
        { name: 'nextauth-secret', value: nextAuthSecret }
        { name: 'internal-api-token', value: internalApiToken }
      ])
    }
    template: {
      containers: [
        {
          name: 'desk'
          image: webImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'NEXTAUTH_URL', value: 'https://${namePrefix}.${environment.properties.defaultDomain}' }
            { name: 'NEXTAUTH_SECRET', secretRef: 'nextauth-secret' }
            { name: 'LINKEDIN_CLIENT_ID', value: linkedinClientId }
            { name: 'LINKEDIN_CLIENT_SECRET', secretRef: 'linkedin-client-secret' }
            { name: 'GMG_API_URL', value: apiUrl }
            { name: 'GMG_INTERNAL_TOKEN', secretRef: 'internal-api-token' }
            { name: 'GMG_WHATSAPP_ENABLED', value: whatsappEnabled ? '1' : '0' }
          ]
          probes: [startupProbe, readinessProbe, livenessProbe]
        }
        {
          name: 'api'
          image: apiImage
          command: ['python3', '-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000']
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: concat([
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'GMG_BLOB_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
            { name: 'GMG_QUOTA_TABLE_URL', value: storage.properties.primaryEndpoints.table }
            { name: 'GMG_EXPERTISE_TABLE_URL', value: storage.properties.primaryEndpoints.table }
            { name: 'GMG_REQUIRE_API_TOKEN', value: '1' }
            { name: 'GMG_INTERNAL_TOKEN', secretRef: 'internal-api-token' }
            { name: 'GMG_INFERENCE_PROVIDER', value: 'azure-openai' }
            { name: 'GMG_FOUNDRY_ENDPOINT', value: foundryEndpoint }
            { name: 'GMG_INFERENCE_AUTHORIZED_UNTIL', value: inferenceAuthorizedUntil }
            { name: 'GMG_INFERENCE_DAILY_CALLS', value: string(dailyCalls) }
            { name: 'GMG_INFERENCE_MONTHLY_CALLS', value: string(monthlyCalls) }
            { name: 'QUERY_LOG_PATH', value: '/tmp/gmg-queries.jsonl' }
            { name: 'UI_ORIGINS', value: '' }
          ], whatsappEnabled ? [
            { name: 'GMG_WHATSAPP_ENABLED', value: '1' }
            { name: 'GMG_WHATSAPP_PHONE_NUMBER_ID', value: whatsappPhoneNumberId }
            { name: 'GMG_WHATSAPP_APP_SECRET', secretRef: 'whatsapp-app-secret' }
            { name: 'GMG_WHATSAPP_VERIFY_TOKEN', secretRef: 'whatsapp-verify-token' }
            { name: 'GMG_WHATSAPP_ACCESS_TOKEN', secretRef: 'whatsapp-access-token' }
            { name: 'GMG_WHATSAPP_TESTERS', secretRef: 'whatsapp-testers' }
            { name: 'GMG_WHATSAPP_DESK_URL', value: 'https://${namePrefix}.${environment.properties.defaultDomain}/login' }
            { name: 'GMG_WHATSAPP_MONTHLY_LIMIT', value: string(whatsappMonthlyLimit) }
          ] : [])
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output appUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
output linkedinCallback string = 'https://${app.properties.configuration.ingress.fqdn}/api/auth/callback/linkedin'
