// Azure AI Foundry project + model deployment infrastructure
// Deploy with: az deployment group create -g <rg> -f infra/main.bicep

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name for the Foundry account')
param accountName string

@description('Name of the AI project')
param projectName string

@description('Azure OpenAI model deployment name')
param gptDeploymentName string = 'gpt-4o-2024-11-20'

@description('OpenAI model name')
param gptModelName string = 'gpt-4o'

@description('OpenAI model version')
param gptModelVersion string = '2024-11-20'

@description('SKU capacity (tokens-per-minute in thousands)')
param gptCapacity int = 30

// --- Cognitive Services account (hosts the Foundry project) ---
resource aiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
  }
}

// --- AI Project ---
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2024-10-01' = {
  parent: aiAccount
  name: projectName
  location: location
  properties: {}
}

// --- GPT model deployment ---
resource gptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiAccount
  name: gptDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: gptCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: gptModelName
      version: gptModelVersion
    }
  }
}

// --- Outputs ---
output projectEndpoint string = 'https://${aiAccount.properties.endpoint}/api/projects/${projectName}'
output accountId string = aiAccount.id
output projectId string = aiProject.id
output gptDeploymentId string = gptDeployment.id
