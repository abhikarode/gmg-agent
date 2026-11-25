targetScope = 'resourceGroup'

@minLength(2)
@maxLength(64)
param foundryName string
param runtimeIdentityName string

@description('Pay-per-token capacity units for the grant-approved GPT-6 Luna deployment.')
@minValue(1)
param capacity int = 10

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryName
  location: 'eastus'
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: foundryName
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: runtimeIdentityName
}

resource inferenceCaller 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, identity.id, 'azure-openai-inference')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: 'gmg-agent'
  location: 'eastus'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'GMG Agent'
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: 'gpt-6-luna'
  sku: {
    name: 'DataZoneStandard'
    capacity: capacity
  }
  properties: {
    model: {
      name: 'gpt-6-luna'
      format: 'OpenAI'
      version: '2026-09-22'
    }
    versionUpgradeOption: 'NoAutoUpgrade'
  }
  dependsOn: [project]
}

output foundryEndpoint string = 'https://${foundryName}.services.ai.azure.com'
