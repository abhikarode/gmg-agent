targetScope = 'resourceGroup'

param location string = 'westus3'
param runtimeIdentityName string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: runtimeIdentityName
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: 'gmg${uniqueString(resourceGroup().id, runtimeIdentityName)}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    policies: {
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
  }
}

resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'AcrPull')
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

output registryName string = registry.name
output loginServer string = registry.properties.loginServer
