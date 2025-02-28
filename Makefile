# Variables
PKG_NAME      = unicon.plugins
BUILD_DIR     = $(shell pwd)/__build__
DIST_DIR      = $(BUILD_DIR)/dist
SOURCEDIR     = .
PYTHON        = python3
TESTCMD       = runAll --path=tests/
BUILD_CMD     = $(PYTHON) setup.py bdist_wheel --dist-dir=$(DIST_DIR)
PYPIREPO      = pypitest


DEPENDENCIES = robotframework pyyaml dill coverage Sphinx \
			   sphinxcontrib-napoleon sphinxcontrib-mockautodoc \
			   sphinx-rtd-theme asyncssh PrettyTable "cryptography>=43.0"


.PHONY: clean package distribute develop undevelop help devnet\
        docs test install_build_deps uninstall_build_deps distribute_staging\
        distribute_staging_external

help:
	@echo "Please use 'make <target>' where <target> is one of"
	@echo ""
	@echo "package                        Build the package"
	@echo "test                           Test the package"
	@echo "distribute                     Distribute the package to internal Cisco PyPi server"
	@echo "distribute_staging             Distribute build pkgs to staging area"
	@echo "distribute_staging_external    Distribute build pkgs to external staging area"
	@echo "clean                          Remove build artifacts"
	@echo "develop                        Build and install development package"
	@echo "undevelop                      Uninstall development package"
	@echo "docs                           Build Sphinx documentation for this package"
	@echo "install_build_deps             does nothing - just following pyATS pkg standard"
	@echo "uninstall_build_deps           does nothing - just following pyATS pkg standard"
	@echo "changelogs			          Build compiled changelog file"
	@echo ""

install_build_deps:
	@pip install --upgrade pip setuptools wheel
	@echo ""
	@echo "Done."
	@echo ""

uninstall_build_deps:
	@echo ""

html: docs

docs:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Building $(PKG_NAME) documentation for preview: $@"
	@echo ""

	python3 docs/gen_dialogs_rst.py > docs/user_guide/services/service_dialogs.rst
	sphinx-build -b html -c docs -d ./__build__/documentation/doctrees docs/ ./__build__/documentation/html

	@echo "Completed building docs for preview."
	@echo ""
	@echo "Done."
	@echo ""

test:
	@$(TESTCMD)

package:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Building $(PKG_NAME) distributable: $@"
	@echo ""

	$(BUILD_CMD)

	@echo ""
	@echo "Completed building: $@"
	@echo ""
	@echo "Done."
	@echo ""

develop:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Building and installing $(PKG_NAME) development distributable: $@"
	@echo ""
	@pip uninstall -y $(PKG_NAME)
	@pip install $(DEPENDENCIES)
	@pip install -e . --no-deps
	@echo ""
	@echo "Completed building and installing: $@"
	@echo ""
	@echo "Done."
	@echo ""

undevelop:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Uninstalling $(PKG_NAME) development distributable: $@"
	@echo ""

	@pip uninstall $(PKG_NAME) -y

	@echo ""
	@echo "Completed uninstalling: $@"
	@echo ""
	@echo "Done."
	@echo ""

clean:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Removing make directory: $(BUILD_DIR)"
	@rm -rf $(BUILD_DIR) $(DIST_DIR)
	@echo ""
	@echo "Removing build artifacts ..."
	@$(PYTHON) setup.py clean
	@echo ""
	@echo "Done."
	@echo ""

distribute:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(PROD_PKGS)"
	@test -d $(DIST_DIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(PROD_PKGS)/$(PKG_NAME) || mkdir $(PROD_PKGS)/$(PKG_NAME)'
	@scp $(DIST_DIR)/* $(PROD_USER):$(PROD_PKGS)/$(PKG_NAME)/
	@echo ""
	@echo "Done."
	@echo ""

distribute_staging:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(STAGING_PKGS)"
	@test -d $(DIST_DIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(STAGING_PKGS)/$(PKG_NAME) || mkdir $(STAGING_PKGS)/$(PKG_NAME)'
	@scp $(DIST_DIR)/* $(PROD_USER):$(STAGING_PKGS)/$(PKG_NAME)/
	@echo ""
	@echo "Done."
	@echo ""

distribute_staging_external:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Copying all distributable to $(STAGING_EXT_PKGS)"
	@test -d $(DIST_DIR) || { echo "Nothing to distribute! Exiting..."; exit 1; }
	@ssh -q $(PROD_USER) 'test -e $(STAGING_EXT_PKGS)/$(PKG_NAME) || mkdir $(STAGING_EXT_PKGS)/$(PKG_NAME)'
	@scp $(DIST_DIR)/* $(PROD_USER):$(STAGING_EXT_PKGS)/$(PKG_NAME)/
	@echo ""
	@echo "Done."
	@echo ""

changelogs:
	@echo ""
	@echo "--------------------------------------------------------------------"
	@echo "Generating changelog file"
	@echo ""
	@python3 -c "from ciscodistutils.make_changelog import main; main('./docs/changelog/undistributed', './docs/changelog/undistributed.rst')"
	@python3 -c "from ciscodistutils.make_changelog import main; main('./docs/changelog_plugins/undistributed', './docs/changelog_plugins/undistributed.rst')"
	@echo ""
	@echo "Done."
	@echo ""
