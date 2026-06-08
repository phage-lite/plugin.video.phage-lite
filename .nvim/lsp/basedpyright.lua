local cfg = {
    basedpyright = {
        settings = {
            basedpyright = {
                analysis = {
                    typeCheckingMode = "standard",
                    autoSearchPaths = true,
                    useLibraryCodeForTypes = true,
                },
                inlayHints = {
                    variableTypes = true,
                    returnTypes = true,
                    callArgumentNames = true,
                    pytestParameters = true,
                },
            },
        },
    },
    ruff = {
        on_attach = function(client)
            client.server_capabilities.hoverProvider = false
        end,
    },
}

for server_name, server_config in pairs(cfg) do
    vim.lsp.config(server_name, server_config)
end
