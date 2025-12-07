package sanity;

public class SanityCheck {

    public static void main(String[] args) {
        String message = "Пользователь не найден. Проверьте логин и попробуйте ещё раз.";
        System.out.println(message);

        // Это однострочный комментарий, который тоже должен быть переведён.
        /*
         * И это многострочный комментарий, описывающий поведение системы.
         * Он тоже должен быть переведён, но структура кода меняться не должна.
         */
    }
}

package ru.webc.cwpam.common.dto.data;

import com.google.common.base.MoreObjects;
import com.google.common.base.Objects;
import com.google.common.base.Strings;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import ru.webc.cwpam.common.shared.HasUniqueName;
import ru.webc.cwpam.common.util.StringUtil;

import static com.google.common.base.Preconditions.checkNotNull;

@ApiModel(value = "CredentialDto", description = "<p>Привилегированная учетная запись.</p>" +
        "<p>Правила при создании/изменении Привилегированной УЗ:</p>" +
        "<ul>" +
        "<li>Идентификатор (атрибут id) - уникальная строка из латинских символов в нижнем регистре, цифр, " +
        "знаков \"-\" и \"/\", без пробелов.</li>" +
        "<li>Если задан пароль (атрибут password), то обращение за паролем в Lieberman API не осуществляется " +
        "и в сеансах используется указанный пароль.</li>" +
        "<li>Признак exclusive = true запрещает открытие сеансов в том же приложении с другими " +
        "привилегированными УЗ (функционал вкладок).</li>" +
        "<li>Атрибут-признак userAccountId определяет, что УЗ является \"именной\" для данного пользователя." +
        "</li>" +
        "<li>Атрибут-признак adminObjectId определяет, что УЗ является \"локальной\" для данного объекта " +
        "администрирования.</li>" +
        "</ul>")
public class CredentialDto extends AbstractDto implements HasUniqueName {

    public static final short SPIN_MODE_OFF = -1;

    static final long serialVersionUID = 1L;

    @ApiModelProperty(value = "Имя Привилегированной УЗ (уникальное)", allowEmptyValue = false)
    private String name = "";

    @ApiModelProperty(value = "Строка интеграции Lieberman", allowEmptyValue = true)
    private String liebermanKey = "";

    @ApiModelProperty(value = "Короткое имя Домена", allowEmptyValue = true)
    private String domainName = "";

    @ApiModelProperty(value = "FQDN домена", allowEmptyValue = true)
    private String domainFqdn = "";

    @ApiModelProperty(value = "Имя пользователя Привилегированной УЗ", allowEmptyValue = false)
    private String username = "";

    @ApiModelProperty(value = "Зашифрованный пароль Привилегированной УЗ", allowEmptyValue = true)
    private String secret = "";

    @ApiModelProperty(value = "Признак запуска сеанса с данной Привилегированной УЗ в эксклюзивном режиме",
            allowEmptyValue = true)
    private boolean exclusive = false;

    @ApiModelProperty(value = "Идентификатор Агента паролей", allowEmptyValue = true)
    private String passwordAgentId = "";

    @ApiModelProperty(value = "<p>Способ рандомизации пароля Привилегированной УЗ:<br/>" +
            "\"-1\" – рандомизация отключена (значение по умолчанию)<br/>" +
            "\"0\" – после начала сеанса<br/>" +
            "\"1\" – после завершения сеанса<br/>" +
            "\"2\" – по расписанию<br/>" +
            "\"3\" – перед началом сеанса<br/></p>", allowEmptyValue = true)
    private Short spinMode = SPIN_MODE_OFF;

    @ApiModelProperty(value = "Идентификатор УЗ пользователя, для которой Привилегированная УЗ считается именной",
            allowEmptyValue = true)
    private String userAccountId = "";

    @ApiModelProperty(value = "Идентификатор Объекта администрирования (otherid), для которого " +
            "Привилегированная УЗ считается локальной", allowEmptyValue = true)
    private String adminObjectId = "";

    public CredentialDto() {
    }

    public CredentialDto(String id) {
        super(checkNotNull(id));
    }

    /**
     * <p>Конструктор устанавливает обязательные поля.</p>
     *
     * @param id       идентификатор
     * @param name     имя привилегированной УЗ
     * @param username имя пользователя привилегированной УЗ
     */
    public CredentialDto(String id, String name, String username) {
        this(id);
        this.name = checkNotNull(name);
        this.username = checkNotNull(username);
    }

    /**
     * <p>Возвращает имя УЗ (Credential.name, уникальное).</p>
     *
     * @return name
     */
    public String getName() {
        return name;
    }

    /**
     * <p>Устанавливает имя УЗ (Credential.name, уникальное).</p>
     *
     * @param name имя УЗ
     */
    public void setName(String name) {
        this.name = Strings.nullToEmpty(name);
    }

    /**
     * <p>Возвращает строку интеграции Lieberman (Credential.liebermanKey).</p>
     *
     * @return liebermanKey
     */
    public String getLiebermanKey() {
        return liebermanKey;
    }

    /**
     * <p>Устанавливает строку интеграции Lieberman (Credential.liebermanKey).</p>
     *
     * @param liebermanKey строка интеграции Lieberman
     */
    public void setLiebermanKey(String liebermanKey) {
        this.liebermanKey = Strings.nullToEmpty(liebermanKey);
    }

    /**
     * <p>Возвращает короткое имя домена (Credential.domainName).</p>
     *
     * @return domainName
     */
    public String getDomainName() {
        return domainName;
    }

    /**
     * <p>Устанавливает короткое имя домена (Credential.domainName).</p>
     *
     * @param domainName короткое имя домена
     */
    public void setDomainName(String domainName) {
        this.domainName = Strings.nullToEmpty(domainName);
    }

    /**
     * <p>Возвращает FQDN домена (Credential.domainFqdn).</p>
     *
     * @return domainFqdn
     */
    public String getDomainFqdn() {
        return domainFqdn;
    }

    /**
     * <p>Устанавливает FQDN домена (Credential.domainFqdn).</p>
     *
     * @param domainFqdn FQDN домена
     */
    public void setDomainFqdn(String domainFqdn) {
        this.domainFqdn = Strings.nullToEmpty(domainFqdn);
    }

    /**
     * <p>Возвращает имя пользователя привилегированной УЗ (Credential.username).</p>
     *
     * @return username
     */
    public String getUsername() {
        return username;
    }

    /**
     * <p>Устанавливает имя пользователя привилегированной УЗ (Credential.username).</p>
     *
     * @param username имя пользователя
     */
    public void setUsername(String username) {
        this.username = Strings.nullToEmpty(username);
    }

    /**
     * <p>Возвращает зашифрованный пароль привилегированной УЗ (Credential.password).</p>
     *
     * @return secret
     */
    public String getSecret() {
        return secret;
    }

    /**
     * <p>Устанавливает зашифрованный пароль привилегированной УЗ (Credential.password).</p>
     *
     * @param secret пароль
     */
    public void setSecret(String secret) {
        this.secret = Strings.nullToEmpty(secret);
    }

    /**
     * <p>Возвращает признак запуска сеанса с данной УЗ в эксклюзивном режиме (Credential.exclusive).</p>
     *
     * @return exclusive
     */
    public boolean isExclusive() {
        return exclusive;
    }

    /**
     * <p>Устанавливает признак запуска сеанса с данной УЗ в эксклюзивном режиме (Credential.exclusive).</p>
     *
     * @param exclusive признак
     */
    public void setExclusive(boolean exclusive) {
        this.exclusive = exclusive;
    }

    /**
     * <p>Возвращает идентификатор Агента паролей (PasswordAgent.id).</p>
     *
     * @return passwordAgentId
     */
    public String getPasswordAgentId() {
        return passwordAgentId;
    }

    /**
     * <p>Устанавливает идентификатор Агента паролей (PasswordAgent.id).</p>
     *
     * @param passwordAgentId идентификатор Агента паролей
     */
    public void setPasswordAgentId(String passwordAgentId) {
        this.passwordAgentId = passwordAgentId;
    }

    /**
     * <p>Возвращает способ рандомизации пароля (Credential.spinMode):</p>
     * <p><b>-1</b> – рандомизация отключена</p>
     * <p><b>0</b> – после начала сеанса</p>
     * <p><b>1</b> – после завершения сеанса</p>
     * <p><b>2</b> – по расписанию</p>
     * <p><b>3</b> – перед началом сеанса</p>
     *
     * @return spinMode
     */
    public Short getSpinMode() {
        return spinMode;
    }

    /**
     * <p>Устанавливает способ рандомизации пароля (Credential.spinMode):</p>
     * <p><b>-1</b> – рандомизация отключена</p>
     * <p><b>0</b> – после начала сеанса</p>
     * <p><b>1</b> – после завершения сеанса</p>
     * <p><b>2</b> – по расписанию</p>
     * <p><b>3</b> – перед началом сеанса</p>
     *
     * @param spinMode способ рандомизации пароля
     */
    public void setSpinMode(Short spinMode) {
        this.spinMode = spinMode;
    }

    /**
     * <p>Возвращает идентификатор УЗ пользователя для именной привилегированной УЗ (UserAccount.id).</p>
     *
     * @return userAccountId
     */
    public String getUserAccountId() {
        return userAccountId;
    }

    /**
     * <p>Устанавливает идентификатор УЗ пользователя для именной привилегированной УЗ (UserAccount.id).</p>
     *
     * @param userAccountId идентификатор УЗ
     */
    public void setUserAccountId(String userAccountId) {
        this.userAccountId = Strings.nullToEmpty(userAccountId);
    }

    /**
     * <p>Возвращает идентификатор объекта администрирования (otherid) для привилегированной УЗ связанной
     * с конкретным объектом (AdminObject.otherid).</p>
     *
     * @return adminObjectId
     */
    public String getAdminObjectId() {
        return adminObjectId;
    }

    /**`
     * <p>Устанавливает идентификатор объекта администрирования (otherid) для привилегированной УЗ связанной
     * с конкретным объектом (AdminObject.otherid).</p>
     *
     * @param adminObjectId идентификатор объекта администрирования
     */
    public void setAdminObjectId(String adminObjectId) {
        this.adminObjectId = Strings.nullToEmpty(adminObjectId);
    }

    @Override
    public boolean validate() {
        boolean hasPassword = !Strings.isNullOrEmpty(getSecret())
                || (!Strings.isNullOrEmpty(getLiebermanKey()) && !Strings.isNullOrEmpty(getPasswordAgentId()));
        return !StringUtil.isNullOrHasLeadingOrTrailingSpaces(getName())
                && !StringUtil.isNullOrHasLeadingOrTrailingSpaces(getUsername())
                && hasPassword;
    }

    @Override
    public boolean equals(Object object) {
        if (this == object) return true;
        if (object == null) return false;
        if (!(object instanceof CredentialDto)) return false;
        CredentialDto other = (CredentialDto) object;
        return Objects.equal(this.getId(), other.getId())
                && Objects.equal(this.getName(), other.getName())
                && Objects.equal(this.getDomainName(), other.getDomainName())
                && Objects.equal(this.getDomainFqdn(), other.getDomainFqdn())
                && Objects.equal(this.getUsername(), other.getUsername())
                && Objects.equal(this.getSecret(), other.getSecret())
                && Objects.equal(this.getLiebermanKey(), other.getLiebermanKey())
                && Objects.equal(this.isExclusive(), other.isExclusive())
                && Objects.equal(this.getPasswordAgentId(), other.getPasswordAgentId())
                && Objects.equal(this.getSpinMode(), other.getSpinMode())
                && Objects.equal(this.getUserAccountId(), other.getUserAccountId())
                && Objects.equal(this.getAdminObjectId(), other.getAdminObjectId());
    }

    @Override
    public int hashCode() {
        return Objects.hashCode(super.hashCode(), name, liebermanKey, domainName, domainFqdn, username, secret, exclusive, passwordAgentId, spinMode, userAccountId, adminObjectId);
    }

    @Override
    public String toString() {
        return MoreObjects.toStringHelper(this.getClass())
                .add("id", getId())
                .add("name", getName())
                .add("domainName", getDomainName())
                .add("domainFqdn", getDomainFqdn())
                .add("username", getName())
                .add("passwordAgentId", getPasswordAgentId())
                .add("spinMode", getSpinMode())
                .add("liebermanKey", getLiebermanKey())
                .add("userAccountId", getUserAccountId())
                .add("adminObjectId", getAdminObjectId())
                .toString();
    }
}
