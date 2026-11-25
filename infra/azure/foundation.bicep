targetScope = 'resourceGroup'

@description('Azure Container Apps and Storage region.')
param location string = 'westus3'

@minLength(3)
@maxLength(16)
param namePrefix string = 'gmg-agent'

@description('Microsoft Entra object ID of the snapshot publisher. Leave empty to manage the grant separately.')
param snapshotPublisherObjectId string = ''

var storageName = 'gmg${uniqueString(resourceGroup().id, namePrefix)}'
var directoryName = 'gmg-directory'
var tableName = 'gmginference'

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-runtime'
  location: location
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource directory 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: directoryName
  properties: {
    publicAccess: 'None'
  }
}

resource tables 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource quota 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tables
  name: tableName
}

resource expertise 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tables
  name: 'gmgexpertise'
}

resource directoryReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: directory
  name: guid(directory.id, identity.id, 'directory-reader')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  }
}

resource quotaWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: quota
  name: guid(quota.id, identity.id, 'quota-writer')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
  }
}

resource expertiseWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: expertise
  name: guid(expertise.id, identity.id, 'expertise-writer')
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
  }
}

resource directoryPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(snapshotPublisherObjectId)) {
  scope: directory
  name: guid(directory.id, snapshotPublisherObjectId, 'directory-publisher')
  properties: {
    principalId: snapshotPublisherObjectId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

output storageAccountName string = storage.name
output blobAccountUrl string = storage.properties.primaryEndpoints.blob
output tableAccountUrl string = storage.properties.primaryEndpoints.table
output runtimeIdentityName string = identity.name
